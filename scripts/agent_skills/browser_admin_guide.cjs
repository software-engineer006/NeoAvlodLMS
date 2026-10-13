const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { user, installFixtures } = require('./browser_fixtures.cjs');
const catalogue = ['staff:manage', 'subjects:manage', 'groups:read', 'groups:create', 'groups:edit',
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
    assert.equal(count, 22);
    if (width === 1440) {
      for (let index = 0; index < count; index++) {
        await nav.getByRole('button').nth(index).click();
        const image = page.getByRole('article').locator('img');
        await image.scrollIntoViewIfNeeded();
        await image.evaluate((node) => node.decode());
        assert(await image.evaluate((node) => node.naturalWidth > 300 && node.naturalHeight > 200));
        assert(await image.getAttribute('alt'));
        assert(await page.getByRole('list', { name: 'Amaliy qadamlar' }).locator('li').count() >= 3);
      }
    }
    await page.getByLabel('Qo‘llanmadan qidirish').fill('navbat');
    await nav.getByRole('button', { name: /Xabar tarixi/ }).click();
    await page.getByRole('article').locator('img').evaluate((node) => node.decode());
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const exit = await page.locator('header').getByRole('button', { name: 'Chiqish', exact: true }).boundingBox();
    assert(exit.x + exit.width <= width && exit.x >= 0, 'Header exit button must be fully visible');
    fs.mkdirSync('/workspace/.private/ui-acceptance', { recursive: true, mode: 0o700 });
    await page.screenshot({ path: `/workspace/.private/ui-acceptance/admin-guide-${width}.png`, fullPage: true });
    await page.getByRole('button', { name: /Rasmni kattalashtirish/ }).click();
    const dialog = page.getByRole('dialog'); await dialog.waitFor();
    await dialog.locator('img').evaluate((node) => node.decode());
    assert(await dialog.locator('img').evaluate((node) => node.naturalWidth > 0));
    await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'hidden' });
    state.user = { ...user, permissions: catalogue };
    await open();
    assert.equal(await nav.getByRole('button').count(), 20);
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
  console.log('Admin guide browser: superadmin22/fulladmin20/limited6,22 decoded assets, search/zoom,1440/768/360 no overflow/JS error; synthetic only.');
})().catch((error) => { console.error(error.message); process.exit(1); });
