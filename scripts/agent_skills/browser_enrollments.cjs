// Closed synthetic fixtures; never touches runtime students or sends messages.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { user, teacher, group, student, ids, installFixtures } = require('./browser_fixtures.cjs');
const { verifyPreview } = require('./browser_guide_helpers.cjs');
const second = { ...group, id: '00000000-0000-4000-8000-000000000101', name: 'Python namuna', subject_name: 'Python', teacher_name: 'Namuna Ustoz', room_number: '217' };
const third = { ...second, id: '00000000-0000-4000-8000-000000000102', name: 'Python keyingi' };
const enrollment = group => ({ group, is_active: true, level: group.id === ids.group ? 'Elementary' : 'Python boshlang‘ich', mygov_status: group.id === ids.group ? 'o‘tdi' : 'pullik', notes: 'Kursga oid namuna izoh' });
(async () => {
  const browser = await chromium.launch();
  const output = '/workspace/.private/enrol-124/ui'; fs.mkdirSync(output, { recursive: true, mode: 0o700 });
  for (const width of [1440, 768, 360]) {
    for (const portal of ['admin', 'teacher']) {
      const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'Asia/Tashkent' });
      page.setDefaultTimeout(10000);
      const errors = [], mutations = [], profiles = [], metadataEdits = [];
      page.on('pageerror', error => errors.push(error.message));
      const state = { user: portal === 'admin' ? { ...user, role: 'superadmin' } : teacher };
      const unexpected = await installFixtures(page, state);
      let pupil = { ...student, school_name: 'Namuna maktab', enrollments: [enrollment(student.group), enrollment(second)] };
      await page.route('**/api/v1/**', async route => {
        const request = route.request(), url = new URL(request.url()), path = url.pathname;
        if (path.endsWith('/lookups/student-groups')) return route.fulfill({ json: { items: [group, second, third] } });
        if (path === '/api/v1/teacher/groups') return route.fulfill({ json: [group, second] });
        if (path === `/api/v1/teacher/groups/${second.id}`) return route.fulfill({ json: second });
        if (path.endsWith('/students')) {
          const selected = path.includes(second.id) ? second : group;
          return route.fulfill({ json: portal === 'admin' ? { items: [pupil], total: 1, page: 1, page_size: 10 } : [{ ...pupil, group_id: selected.id, group_name: selected.name }] });
        }
        if (path === `/api/v1/admin/students/${ids.student}`) return route.fulfill({ json: pupil });
        if (path === `/api/v1/teacher/students/${ids.student}`) {
          profiles.push(url.searchParams.get('group_id'));
          const selected = url.searchParams.get('group_id') === second.id ? second : group;
          const course = pupil.enrollments.find(item => item.group.id === selected.id);
          return route.fulfill({ json: { ...pupil, enrollments: undefined, group_id: selected.id, group_name: selected.name, subject_name: selected.subject_name || 'English', teacher_name: 'Namuna Ustoz', room_number: selected.room_number, level: course.level, mygov_status: course.mygov_status, notes: course.notes } });
        }
        if (request.method() === 'PUT' && path.includes(`/students/${ids.student}/groups/`)) {
          const key = path.split('/').pop(), data = request.postDataJSON(); mutations.push({ key, ...data });
          const found = pupil.enrollments.find(item => item.group.id === key);
          if (found) found.is_active = data.is_active; else pupil.enrollments.push(enrollment(third));
          return route.fulfill({ json: pupil });
        }
        if (request.method() === 'PATCH' && path.includes(`/students/${ids.student}/groups/`)) {
          const key = path.split('/').pop(), data = request.postDataJSON(); metadataEdits.push({ key, ...data });
          Object.assign(pupil.enrollments.find(item => item.group.id === key), data);
          return route.fulfill({ json: pupil });
        }
        return route.fallback();
      });
      await page.goto(`http://${portal}:${portal === 'admin' ? 3000 : 3001}`);
      async function nav(name) {
        const button = page.getByRole('button', { name, exact: true });
        if (!await button.isVisible()) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
        await button.click();
      }
      if (portal === 'admin') {
        await nav('O‘quvchilar'); await page.getByText('Namuna O‘quvchi', { exact: true }).click();
        const dialog = page.getByRole('dialog'), panel = dialog.getByRole('region', { name: 'O‘quvchi guruhlari' });
        await panel.getByText(second.name, { exact: true }).waitFor();
        await panel.getByLabel('Qo‘shimcha guruh').selectOption(third.id);
        await panel.getByRole('button', { name: 'Guruhga biriktirish', exact: true }).click();
        await panel.getByText(third.name, { exact: true }).waitFor();
        await panel.locator('article').filter({ hasText: third.name }).getByRole('button', { name: 'Guruhdan olish' }).click();
        assert.equal(mutations.length, 1);
        await panel.getByRole('button', { name: 'Biriktirishni olish' }).click();
        await panel.getByText('Oldingi guruh', { exact: true }).waitFor();
        assert.deepEqual(mutations, [{ key: third.id, is_active: true }, { key: third.id, is_active: false }]);
        assert(await panel.getByText(second.name, { exact: true }).isVisible());
        const course = panel.locator('article').filter({ hasText: 'English A' });
        await course.getByRole('button', { name: 'Kurs ma’lumotlarini tahrirlash' }).click();
        await course.getByLabel('Daraja', { exact: true }).fill('Beginner');
        await course.getByLabel('MyGov holati', { exact: true }).fill('qayta topshiradi');
        await course.getByLabel('Kurs izohi', { exact: true }).fill('Yangi namuna izoh');
        await course.getByRole('button', { name: 'Kurs ma’lumotlarini saqlash' }).click();
        await course.getByText('Yangi namuna izoh', { exact: true }).waitFor();
        assert.deepEqual(metadataEdits, [{ key: ids.group, level: 'Beginner', mygov_status: 'qayta topshiradi', notes: 'Yangi namuna izoh' }]);
        await page.screenshot({ path: `${output}/admin-groups-${width}.png`, fullPage: true });
        await page.keyboard.press('Escape');
        state.user = { ...user, permissions: ['students:read'] };
        await page.reload(); await nav('O‘quvchilar'); await page.getByText('Namuna O‘quvchi', { exact: true }).click();
        await page.getByRole('region', { name: 'O‘quvchi guruhlari' }).waitFor();
        assert.equal(await page.getByLabel('Qo‘shimcha guruh').count(), 0);
        assert.equal(await page.getByRole('button', { name: 'Kurs ma’lumotlarini tahrirlash' }).count(), 0);
        state.user = { ...user, role: 'superadmin' }; await page.reload();
      } else {
        await nav('Mening guruhlarim');
        await page.getByRole('button', { name: 'O‘quvchilar', exact: true }).nth(1).click();
        await page.getByText('Namuna O‘quvchi', { exact: true }).click();
        await page.getByRole('dialog').getByText(second.name, { exact: true }).first().waitFor();
        assert.equal(profiles.at(-1), second.id); assert.equal(mutations.length, 0);
        await page.getByRole('dialog').getByText('Python boshlang‘ich', { exact: true }).waitFor();
        await page.getByRole('dialog').getByText('pullik', { exact: true }).waitFor();
        assert.equal(await page.getByRole('dialog').getByText('Elementary', { exact: true }).count(), 0);
        await page.screenshot({ path: `${output}/teacher-context-${width}.png`, fullPage: true });
      }
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${portal}${width}: overflow`);
      await page.keyboard.press('Escape'); await nav('Qo‘llanma');
      await page.getByLabel('Qo‘llanmadan qidirish').fill(portal === 'admin' ? 'Profilni tahrirlash' : 'O‘quvchi profili');
      await page.getByRole('navigation', { name: 'Qo‘llanma mavzulari' }).getByRole('button').first().click();
      await verifyPreview(page);
      assert.deepEqual(unexpected, []); assert.deepEqual(errors, []); await page.close();
    }
  }
  await browser.close(); console.log('Enrollment UI: two courses/one profile, add/remove confirmation, read-only grants, selected teacher context and guide,1440/768/360; closed fixtures only.');
})().catch(error => { console.error(error.stack); process.exit(1); });
