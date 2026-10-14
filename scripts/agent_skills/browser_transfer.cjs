// Closed synthetic selected-course transfer acceptance; no runtime mutation.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { ids, user, group, student, installFixtures } = require('./browser_fixtures.cjs');
const { verifyPreview } = require('./browser_guide_helpers.cjs');
const source = { ...group, id: '00000000-0000-4000-8000-000000000101', name: 'Python A' };
const target = { ...source, id: '00000000-0000-4000-8000-000000000102', name: 'Python B' };
(async () => {
  const browser = await chromium.launch();
  const output = '/workspace/.private/transfer-131/ui'; fs.mkdirSync(output, { recursive: true, mode: 0o700 });
  for (const width of [1440, 768, 360]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'Asia/Tashkent' });
    const state = { user: { ...user, role: 'superadmin' } }, errors = [], writes = [];
    page.on('pageerror', error => errors.push(error.message));
    const unexpected = await installFixtures(page, state);
    let pupil = { ...student, enrollments: [student.group, source].map(group => ({ group, is_active: true, level: null, mygov_status: null, notes: null })) };
    await page.route('**/api/v1/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/lookups/student-groups')) return route.fulfill({ json: { items: [group, source, target] } });
      if (path === '/api/v1/admin/students') return route.fulfill({ json: { items: [pupil], total: 1, page: 1, page_size: 10 } });
      if (path === `/api/v1/admin/students/${ids.student}/transfer`) {
        const body = route.request().postDataJSON(); writes.push(body);
        pupil.enrollments[1].is_active = false;
        pupil.enrollments.push({ ...pupil.enrollments[1], group: target, is_active: true });
        return route.fulfill({ json: pupil });
      }
      return route.fallback();
    });
    async function nav(name) {
      const button = page.getByRole('button', { name, exact: true });
      if (!await button.isVisible()) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
      await button.click();
    }
    await page.goto('http://admin:3000'); await nav('O‘quvchilar');
    await page.getByTitle('Guruhni ko‘chirish').click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Qaysi guruhdan ko‘chirish').selectOption(source.id);
    await dialog.getByLabel('Yangi guruhni tanlang', { exact: false }).locator(`option[value="${target.id}"]`).waitFor({ state: 'attached' });
    await dialog.getByLabel('Yangi guruhdan qidirish').fill('Python B');
    await dialog.getByLabel('Yangi guruhni tanlang', { exact: false }).selectOption(target.id);
    await dialog.getByRole('button', { name: 'Guruhga ko‘chirish' }).click();
    await dialog.getByText('Ko‘chirish sababini kiriting', { exact: true }).waitFor(); assert.equal(writes.length, 0);
    await dialog.getByLabel('Ko‘chirish sababi', { exact: false }).fill('Jadval moslashdi');
    await page.screenshot({ path: `${output}/transfer-${width}.png`, fullPage: true });
    await dialog.getByRole('button', { name: 'Guruhga ko‘chirish' }).click();
    await dialog.waitFor({ state: 'hidden' });
    assert.deepEqual(writes, [{ source_group_id: source.id, target_group_id: target.id, reason: 'Jadval moslashdi' }]);
    assert.equal(pupil.parent_id, ids.parent); assert.equal(pupil.group_id, ids.group);
    assert.deepEqual(pupil.enrollments.filter(e => e.is_active).map(e => e.group.id), [ids.group, target.id]);
    state.user = { ...user, permissions: ['students:read'] }; await page.reload(); await nav('O‘quvchilar');
    assert.equal(await page.getByTitle('Guruhni ko‘chirish').count(), 0);
    state.user = { ...user, role: 'superadmin' }; await page.reload(); await nav('Qo‘llanma');
    await page.getByLabel('Qo‘llanmadan qidirish').fill('Profilni tahrirlash');
    await page.getByRole('navigation', { name: 'Qo‘llanma mavzulari' }).getByRole('button').first().click();
    await verifyPreview(page);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []); await page.close();
  }
  await browser.close(); console.log('Transfer: selected secondary/reason/search/preserved primary-family/read grant/native guide,1440/768/360 passed; synthetic only.');
})().catch(error => { console.error(error.stack); process.exit(1); });
