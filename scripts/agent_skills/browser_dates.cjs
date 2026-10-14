// Closed synthetic fixtures; no customer login, live writes or messages.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const fixtures = require('./browser_fixtures.cjs');
const { user, teacher, subject, student, campaign, ids, installFixtures } = fixtures;
const at = '2026-12-31T19:00:01.123456Z';
for (const item of [teacher, subject, student, campaign]) item.created_at = at;
const day = '2027-01-01';
const dateTime = '01.01.2027 00:00:01';
const isoPattern = /\b\d{4}-\d{2}(?:-\d{2})?\b/;

async function displayCheck(page, label) {
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${label}: overflow`);
  assert(!isoPattern.test(await page.locator('body').innerText()), `${label}: visible ISO date`);
  for (const input of await page.locator('input:visible').all()) {
    if (['date', 'month'].includes(await input.getAttribute('type'))) continue;
    assert(!isoPattern.test(await input.inputValue()), `${label}: unformatted visible field`);
  }
}
(async () => {
  const browser = await chromium.launch();
  const production = process.argv.includes('--production');
  const output = `/workspace/.private/date-120-ui/${production ? 'production' : 'local'}`;
  fs.mkdirSync(output, { recursive: true, mode: 0o700 });
  for (const [width, timezoneId] of [[1440, 'America/Los_Angeles'], [768, 'Pacific/Kiritimati'], [360, 'UTC']]) {
    for (const portal of ['admin', 'teacher']) {
      const origin = production ? `https://${portal}.eduneo.uz` : `http://${portal}:${portal === 'admin' ? 3000 : 3001}`;
      const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId });
      page.setDefaultTimeout(10000);
      await page.clock.setFixedTime(new Date('2026-12-31T19:00:00Z'));
      const errors = [], calls = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => { if (request.url().includes('/api/')) calls.push(request.url()); });
      const unexpected = await installFixtures(page, { user: portal === 'admin' ? { ...user, role: 'superadmin' } : teacher });
      await page.route(`**/api/v1/admin/staff/${ids.teacher}`, route => route.fulfill({ json: { ...teacher,
        telegram_link: { connected: false, deep_link: 'https://t.me/namuna_bot?start=synthetic', expires_at: at, expired: false } } }));
      await page.route('**/api/v1/admin/attendance?**', route => route.fulfill({ json: { items: [{ id: 'synthetic-record',
        group_id: ids.group, group_name: 'English A', student_id: ids.student, student_name: 'Namuna O‘quvchi',
        date: day, status: 'present', note: null, marked_at: at }], total: 1, page: 1, page_size: 25 } }));
      await page.route('**/api/v1/admin/logs**', route => {
        const url = new URL(route.request().url());
        if (url.pathname.endsWith('/days')) return route.fulfill({ json: [{ day, count: 1 }] });
        return route.fulfill({ json: { items: [{ id: 'date-fixture', at, day, actor: { id: ids.teacher, name: 'Namuna Ustoz', username: 'sample_teacher', role: 'teacher' },
          action: 'attendance.correct', entity: { type: 'attendance', id: 'sample', name: 'Namuna O‘quvchi' },
          changes: { finalized_at: { before: null, after: at } }, private_changed: [], details: { lesson_date: day, reason: 'Namuna tekshiruv' },
          source: 'http', request_id: 'synthetic' }], actors: [], actions: [], total: 1, next_cursor: null, page_size: 50 } });
      });
      await page.goto(origin);
      const nav = async name => {
        const button = page.getByRole('button', { name, exact: true });
        if (!await button.isVisible()) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
        await button.click();
      };
      await nav(portal === 'admin' ? 'Davomat' : 'Davomat olish');
      const input = page.getByRole('textbox', { name: 'Dars sanasi', exact: true });
      await input.waitFor();
      assert.equal(await input.inputValue(), '01.01.2027');
      const request = page.waitForRequest(req => req.url().includes('attendance?date=2027-01-02'));
      await input.fill('02.01.2027'); await request;
      await page.getByRole('button', { name: 'Qoralama saqlash', exact: true }).waitFor();
      const before = calls.length;
      await input.fill('31.02.2027');
      assert.equal(await input.getAttribute('aria-invalid'), 'true');
      const save = page.getByRole('button', { name: 'Qoralama saqlash', exact: true });
      assert(await save.count() === 0 || await save.isDisabled());
      assert.equal(calls.length, before, 'Invalid date produced API requests');
      await input.press('Tab');
      assert.equal(await input.inputValue(), '02.01.2027');
      const native = page.locator('input[type="date"]').first();
      const picked = page.waitForRequest(req => req.url().includes('attendance?date=2027-02-03'));
      await native.fill('2027-02-03', { force: true }); await picked;
      assert.equal(await input.inputValue(), '03.02.2027');
      await page.getByRole('button', { name: 'Dars sanasi — kalendar' }).click();
      await page.keyboard.press('Escape');
      await displayCheck(page, `${portal} attendance ${width}`);
      await page.screenshot({ path: `${output}/${portal}-attendance-${width}.png`, fullPage: true });
      if (portal === 'teacher') {
        await page.getByText(/Tahrirlash muddati:/).waitFor();
        assert(/\d{2}\.\d{2}\.\d{4} 23:59:59/.test(await page.locator('body').innerText()));
        await nav('Davomat tarixi');
      } else {
        await page.getByRole('button', { name: 'Yozuvlar ro‘yxati', exact: true }).click();
        await page.getByText('00:00:01', { exact: true }).waitFor();
        await page.getByText('01.01.2027', { exact: true }).waitFor();
        await displayCheck(page, `admin records ${width}`);
        await page.getByRole('button', { name: 'Oylik jadval (Guruh / Oy)', exact: true }).click();
      }
      const month = page.locator('#month-history-input');
      await month.waitFor(); assert.equal(await month.inputValue(), '01.2027');
      await page.getByRole('columnheader', { name: '31.01.2027', exact: true }).waitFor();
      const history = page.waitForRequest(req => req.url().includes('attendance/history') && req.url().includes('month=2026-12'));
      await month.fill('12.2026'); await history;
      await page.getByRole('columnheader', { name: '31.12.2026', exact: true }).waitFor();
      await displayCheck(page, `${portal} history ${width}`);
      await page.screenshot({ path: `${output}/${portal}-history-${width}.png`, fullPage: true });
      if (portal === 'teacher') {
        await nav('Mening guruhlarim');
        await page.getByRole('button', { name: 'O‘quvchilar', exact: true }).click();
      } else await nav('O‘quvchilar');
      await page.getByText('Namuna O‘quvchi', { exact: true }).click();
      const dialog = page.getByRole('dialog');
      await dialog.getByText('01.01.2027', { exact: true }).waitFor();
      assert.equal(await dialog.getByRole('textbox', { name: 'Oy tanlash' }).inputValue(), '01.2027');
      await dialog.getByRole('textbox', { name: 'Oy tanlash' }).scrollIntoViewIfNeeded();
      await displayCheck(page, `${portal} student ${width}`);
      await page.screenshot({ path: `${output}/${portal}-student-${width}.png`, fullPage: true });
      await page.keyboard.press('Escape');
      if (portal === 'admin') {
        await nav('Fanlar'); await page.getByText('01.01.2027', { exact: true }).waitFor();
        await displayCheck(page, `subjects ${width}`);
        await nav('Xodimlar'); await page.getByTitle('Telegram onboarding havolasi').click();
        await page.getByRole('dialog').getByText(dateTime, { exact: true }).waitFor();
        await displayCheck(page, `telegram expiry ${width}`); await page.keyboard.press('Escape');
        await nav('Xabarlar'); await page.getByRole('tab', { name: 'Yuborishlar tarixi' }).click();
        await page.getByText(dateTime, { exact: true }).waitFor();
        await displayCheck(page, `messages ${width}`);
        await nav('Loglar');
        assert.equal(await page.getByLabel('Log kuni', { exact: true }).inputValue(), '01.01.2027');
        await page.getByText(dateTime, { exact: true }).waitFor();
        await page.getByRole('button', { name: /Davomat tuzatildi tafsilotlari/ }).click();
        await page.getByText('Aniq vaqt va yozuv identifikatori', { exact: true }).click();
        await page.getByText(`Toshkent: ${dateTime}.123456`, { exact: true }).waitFor();
        await displayCheck(page, `logs ${width}`); await page.keyboard.press('Escape');
      }
      await nav('Qo‘llanma');
      const topics = page.getByRole('navigation', { name: 'Qo‘llanma mavzulari' }).getByRole('button');
      await topics.first().waitFor();
      for (let index = 0; index < await topics.count(); index++) {
        await topics.nth(index).click();
        await displayCheck(page, `${portal} guide topic${index} ${width}`);
      }
      assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
      assert(calls.every(url => !url.includes('date=31.02') && !url.includes('date=2027-02-31')));
      await page.close();
      console.log(`${portal} ${width} ${timezoneId}: dates/months/Tashkent rollover, ISO requests, invalid/keyboard/native calendar, profiles/history/guide passed.`);
    }
  }
  await browser.close();
})().catch(error => { console.error(error.stack); process.exit(1); });
