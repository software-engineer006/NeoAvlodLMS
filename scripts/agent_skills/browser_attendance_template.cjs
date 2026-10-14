// Closed synthetic templates; preview never sends a message or uses customer data.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { user, ids, installFixtures } = require('./browser_fixtures.cjs');
const { verifyPreview } = require('./browser_guide_helpers.cjs');
const body = 'NeoAvlod\nFarzandingiz: {student_name}\nGuruh: {group_name}\nSana: {date}\nDars: {lesson_time}\nHolati: {status_label}\n{feedback}';
(async () => {
  const browser = await chromium.launch(), output = '/workspace/.private/template-129/ui';
  fs.mkdirSync(output, { recursive: true, mode: 0o700 });
  for (const width of [1440, 768, 360]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'America/Los_Angeles' });
    page.setDefaultTimeout(10000);
    const state = { user: { ...user, role: 'superadmin' } }, errors = [], writes = [];
    page.on('pageerror', error => errors.push(error.message));
    const unexpected = await installFixtures(page, state);
    let template = { body, version: 1, placeholders: ['student_name','group_name','date','lesson_time','status_label','feedback'],
      preview: 'Namuna O‘quvchi · 14.10.2026 · 09:00–10:30 · Keldi', updated_at: '2026-10-14T10:00:00Z', changed_by: ids.admin, editor_name: 'Namuna Administrator' };
    await page.route('**/api/v1/admin/attendance/message-template**', route => {
      const request = route.request(), method = request.method();
      if (method === 'POST') return route.fulfill({ json: { message: 'Yangi namuna ·14.10.2026 ·09:00–10:30 ·Keldi' } });
      if (method === 'PUT') { const data = request.postDataJSON(); writes.push(data); template = { ...template, body: data.body, version: 2 }; }
      return route.fulfill({ json: template });
    });
    async function nav(name) {
      const button = page.getByRole('button', { name, exact: true });
      if (!await button.isVisible()) await page.getByRole('button', { name: 'Menyuni ochish' }).click(); await button.click();
    }
    await page.goto('http://admin:3000'); await nav('Davomat');
    await page.getByRole('button', { name: 'Xabar shabloni', exact: true }).click();
    await page.getByLabel('Davomat xabari matni').fill(body + '\nNamuna eslatma');
    assert(await page.getByRole('button', { name: 'Shablonni saqlash' }).isDisabled());
    await page.getByRole('button', { name: 'Matnni ko‘rib chiqish' }).click();
    await page.getByText('Yangi namuna ·14.10.2026 ·09:00–10:30 ·Keldi', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Shablonni saqlash' }).click();
    await page.getByText(/Versiya: 2/).waitFor(); assert.equal(writes[0].expected_version, 1);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: `${output}/template-${width}.png`, fullPage: true });
    await nav('Qo‘llanma'); await page.getByLabel('Qo‘llanmadan qidirish').fill('Davomat xabari shablonini');
    await page.getByRole('navigation', { name: 'Qo‘llanma mavzulari' }).getByRole('button').click(); await verifyPreview(page);
    state.user = { ...user, permissions: ['attendance:read'] }; await page.reload(); await nav('Davomat');
    assert.equal(await page.getByRole('button', { name: 'Xabar shabloni', exact: true }).count(), 0);
    assert.deepEqual(unexpected, []); assert.deepEqual(errors, []); await page.close();
  }
  await browser.close(); console.log('Template UI: preview-before-save/version/Tashkent/reader denied/native guide,1440/768/360,no overflow/JS error;closed fixtures.');
})().catch(error => { console.error(error.stack); process.exit(1); });
