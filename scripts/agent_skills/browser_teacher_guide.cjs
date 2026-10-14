const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { teacher, user, installFixtures } = require('./browser_fixtures.cjs');
const { verifyPreview, verifyZoom } = require('./browser_guide_helpers.cjs');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const errors = [];
  for (const width of [1440, 768, 360]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'Asia/Tashkent' });
    page.on('pageerror', (error) => errors.push(error.message));
    const state = { user: teacher, loggedIn: true };
    const unexpected = await installFixtures(page, state);
    await page.goto('http://teacher:3001');
    if (width < 1024) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
    await page.getByRole('button', { name: 'Qo‘llanma', exact: true }).click();
    const nav = page.getByRole('navigation', { name: 'Qo‘llanma mavzulari' });
    await nav.waitFor(); assert.equal(await nav.getByRole('button').count(), 10);
    assert.equal(await nav.getByRole('button', { name: /audit/i }).count(), 0);
    if (width === 1440) for (let index = 0; index < 10; index++) {
      await nav.getByRole('button').nth(index).click();
      await verifyPreview(page);
    }
    await page.getByLabel('Qo‘llanmadan qidirish').fill('chorshanba 23:59');
    await page.getByRole('heading', { name: 'Yakunlangan davomatni 2 kun ichida tuzatish', exact: true }).waitFor();
    await verifyPreview(page);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const exit = await page.locator('header').getByRole('button', { name: 'Chiqish', exact: true }).boundingBox();
    assert(exit.x >= 0 && exit.x + exit.width <= width);
    fs.mkdirSync('/workspace/.private/ui-acceptance', { recursive: true, mode: 0o700 });
    await page.screenshot({ path: `/workspace/.private/ui-acceptance/teacher-guide-${width}.png`, fullPage: true });
    await verifyZoom(page);
    await page.getByRole('button', { name: 'Bo‘limga o‘tish', exact: true }).click();
    await page.getByRole('textbox', { name: 'Dars sanasi', exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Xodimlar', exact: true }).count(), 0);
    state.user = { ...user, role: 'superadmin' }; await page.reload();
    await page.getByText(/Ruxsat berilmagan/).first().waitFor();
    assert.equal(await page.getByLabel('Qo‘llanmadan qidirish').count(), 0);
    assert.deepEqual(unexpected, []); await page.close();
  }
  await browser.close(); assert.deepEqual(errors, []);
  console.log('Teacher React guide:10 topics/all markers/inert controls, correction reason/boundary/search/zoom/destination,admin-denied,1440/768/360 no overflow/JS error; synthetic only.');
})().catch((error) => { console.error(error.message); process.exit(1); });
