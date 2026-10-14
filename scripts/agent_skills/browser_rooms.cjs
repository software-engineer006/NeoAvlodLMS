// Closed synthetic room/course fixtures; no real database mutations.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { user, teacher, group, subject, ids, installFixtures } = require('./browser_fixtures.cjs');
const { verifyPreview } = require('./browser_guide_helpers.cjs');
const roomId = '00000000-0000-4000-8000-000000000217';
(async () => {
  const browser = await chromium.launch(), output = '/workspace/.private/rooms-127/ui';
  fs.mkdirSync(output, { recursive: true, mode: 0o700 });
  for (const width of [1440, 768, 360]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'America/Los_Angeles' });
    page.setDefaultTimeout(10000);
    const errors = [], writes = [], state = { user: { ...user, role: 'superadmin' } };
    page.on('pageerror', error => errors.push(error.message));
    const unexpected = await installFixtures(page, state);
    let rooms = [{ id: roomId, name: '217', description: 'Namuna kompyuter xonasi', is_active: true, created_at: '2026-10-14T10:00:00Z', updated_at: '2026-10-14T10:00:00Z' }];
    let course = { ...group, room_id: null, room_number: null };
    await page.route('**/api/v1/**', async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname, method = request.method();
      if (path.endsWith('/lookups/group-options')) return route.fulfill({ json: { subjects: [subject], teachers: [teacher], rooms } });
      if (path === '/api/v1/admin/rooms') {
        if (method === 'GET') return route.fulfill({ json: rooms });
        const body = request.postDataJSON(); writes.push([method, path, body]);
        const created = { ...rooms[0], ...body, id: ids.subject }; rooms.push(created);
        return route.fulfill({ status: 201, json: created });
      }
      if (path.startsWith('/api/v1/admin/rooms/')) {
        const key = path.split('/').pop(), room = rooms.find(item => item.id === key);
        if (method === 'DELETE') {
          writes.push([method, path]);
          if (course.room_id === key) return route.fulfill({ status: 409, json: { detail: 'Guruh biriktirilgan xonani o‘chirib bo‘lmaydi' } });
          rooms = rooms.filter(item => item.id !== key); return route.fulfill({ status: 204 });
        }
        const body = request.postDataJSON(); writes.push([method, path, body]); Object.assign(room, body);
        if (course.room_id === key) course.room_number = room.name;
        return route.fulfill({ json: room });
      }
      if (path === '/api/v1/admin/groups') return route.fulfill({ json: { items: [course], total: 1, page: 1, page_size: 10 } });
      if (path === `/api/v1/admin/groups/${ids.group}` && method === 'PATCH') {
        const body = request.postDataJSON(); writes.push([method, path, body]); Object.assign(course, body);
        course.room_number = rooms.find(item => item.id === body.room_id)?.name ?? null;
        return route.fulfill({ json: course });
      }
      if (path === '/api/v1/teacher/groups') return route.fulfill({ json: [{ ...course, room_id: roomId, room_number: '217' }] });
      return route.fallback();
    });
    async function nav(name) {
      const button = page.getByRole('button', { name, exact: true });
      if (!await button.isVisible()) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
      await button.click();
    }
    await page.goto('http://admin:3000'); await nav('Xonalar');
    await page.getByText('Namuna kompyuter xonasi', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Xona qo‘shish' }).click();
    await page.getByLabel('Xona nomi / raqami').fill('218');
    await page.getByLabel('Xona izohi').fill('Yangi namuna xona');
    await page.getByRole('dialog').getByRole('button', { name: 'Saqlash' }).click();
    await page.getByText('Yangi namuna xona', { exact: true }).waitFor();
    await nav('Guruhlar'); await page.getByTitle('Tahrirlash').click();
    await page.getByLabel('Xona', { exact: true }).selectOption(roomId);
    await page.getByRole('dialog').getByRole('button', { name: 'Saqlash' }).click();
    await page.getByRole('dialog').waitFor({ state: 'hidden' }); assert.equal(course.room_id, roomId); assert.equal(course.room_number, '217');
    await nav('Xonalar'); await page.getByRole('button', { name: '217 xonani o‘chirish' }).click();
    await page.getByRole('button', { name: 'O‘chirishni tasdiqlash' }).click();
    await page.getByRole('dialog').getByText('Guruh biriktirilgan xonani o‘chirib bo‘lmaydi', { exact: true }).waitFor();
    await page.getByRole('dialog').getByRole('button', { name: 'Bekor qilish' }).click();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: `${output}/rooms-${width}.png`, fullPage: true });
    await nav('Qo‘llanma'); await page.getByLabel('Qo‘llanmadan qidirish').fill('Xonalarni yaratish');
    await page.getByRole('navigation', { name: 'Qo‘llanma mavzulari' }).getByRole('button').click(); await verifyPreview(page);
    state.user = { ...user, permissions: ['groups:edit'] }; await page.reload();
    if (width < 1024) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
    assert.equal(await page.getByRole('button', { name: 'Xonalar', exact: true }).count(), 0);
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []); assert(writes.some(item => item[0] === 'POST')); await page.close();
    const teacherPage = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'Asia/Tashkent' });
    const teacherUnexpected = await installFixtures(teacherPage, { user: teacher });
    await teacherPage.route('**/api/v1/teacher/groups', route => route.fulfill({ json: [{ ...group, room_number: '217', room_id: roomId }] }));
    await teacherPage.goto('http://teacher:3001');
    const ownGroups = teacherPage.getByRole('button', { name: 'Mening guruhlarim', exact: true });
    if (!await ownGroups.isVisible()) await teacherPage.getByRole('button', { name: 'Menyuni ochish' }).click();
    await ownGroups.click(); await teacherPage.getByText('217', { exact: true }).waitFor();
    assert.equal(await teacherPage.getByRole('button', { name: 'Xonalar', exact: true }).count(), 0);
    assert(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth)); assert.deepEqual(teacherUnexpected, []); await teacherPage.close();
  }
  await browser.close(); console.log('Rooms UI: create/assignment/in-use rejection/Tashkent dates/grants/own teacher schedule/native guide,1440/768/360,closed fixtures.');
})().catch(error => { console.error(error.stack); process.exit(1); });
