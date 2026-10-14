const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { user, installFixtures } = require('./browser_fixtures.cjs');
const { verifyPreview, verifyZoom } = require('./browser_guide_helpers.cjs');
const catalogue = ['staff:manage', 'subjects:manage', 'groups:read', 'groups:create', 'groups:edit',
  'rooms:manage',
  'students:read', 'students:create', 'students:edit', 'attendance:read', 'attendance:write', 'messages:send'];
(async () => {
  const browser = await chromium.launch({ headless: true });
  const failures = [];
  for (const width of [1440, 768, 360]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'Asia/Tashkent' });
    page.on('pageerror', (error) => failures.push(error.message));
    const state = { user: { ...user, role: 'superadmin' }, loggedIn: true };
    const unexpected = await installFixtures(page, state);
    async function open() {
      await page.goto('http://admin:3000');
      if (width < 1024) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
      await page.getByRole('button', { name: 'Qo‘llanma', exact: true }).click();
      await page.getByRole('navigation', { name: 'Qo‘llanma mavzulari' }).waitFor();
    }
    await open();
    const nav = page.getByRole('navigation', { name: 'Qo‘llanma mavzulari' });
    const count = await nav.getByRole('button').count();
    assert.equal(count, 25);
    if (width === 1440) {
      for (let index = 0; index < count; index++) {
        await nav.getByRole('button').nth(index).click();
        await verifyPreview(page);
      }
    }
    await page.getByLabel('Qo‘llanmadan qidirish').fill('navbat');
    await nav.getByRole('button', { name: /Xabar tarixi/ }).click();
    await verifyPreview(page);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const exit = await page.locator('header').getByRole('button', { name: 'Chiqish', exact: true }).boundingBox();
    assert(exit.x + exit.width <= width && exit.x >= 0, 'Header exit button must be fully visible');
    fs.mkdirSync('/workspace/.private/ui-acceptance', { recursive: true, mode: 0o700 });
    await page.screenshot({ path: `/workspace/.private/ui-acceptance/admin-guide-${width}.png`, fullPage: true });
    await verifyZoom(page);
    await page.getByLabel('Qo‘llanmadan qidirish').fill('kunlik loglarni');
    await nav.getByRole('button', { name: /Kunlik loglarni/ }).click();
    await verifyPreview(page);
    await verifyZoom(page);
    state.user = { ...user, permissions: catalogue };
    await open();
    assert.equal(await nav.getByRole('button').count(), 21);
    assert.equal(await nav.getByRole('button', { name: /Kunlik loglarni|Davomat auditi/ }).count(), 0);
    await page.getByLabel('Qo‘llanmadan qidirish').fill('botni sozlash');
    await page.getByText('Mavzu topilmadi', { exact: true }).waitFor();
    state.user = { ...user, permissions: ['groups:read'] };
    await open();
    assert.equal(await nav.getByRole('button').count(), 6);
    await page.getByLabel('Qo‘llanmadan qidirish').fill('Yangi guruh yaratish');
    await page.getByText('Mavzu topilmadi', { exact: true }).waitFor();
    assert.deepEqual(unexpected, []);
    await page.close();
  }
  await browser.close(); assert.deepEqual(failures, []);
  console.log('Admin React guide: superadmin25/fulladmin21/limited6, all scene markers/inert controls, search/zoom/log manual,1440/768/360 no overflow/JS error; synthetic only.');
})().catch((error) => { console.error(error.message); process.exit(1); });
