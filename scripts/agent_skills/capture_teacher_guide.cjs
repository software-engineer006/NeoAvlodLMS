const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { annotate, clearAnnotations } = require('./browser_helpers.cjs');
const { teacher, installFixtures } = require('./browser_fixtures.cjs');
const target = '/workspace/frontend/packages/ui/src/guide/images';
let capturePage;
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, timezoneId: 'Asia/Tashkent' });
  capturePage = page;
  page.on('dialog', async (dialog) => dialog.accept());
  const errors = []; page.on('pageerror', (error) => errors.push(error.message));
  const state = { user: teacher, loggedIn: false, finalized: false };
  const unexpected = await installFixtures(page, state);
  const button = (name) => page.getByRole('button', { name, exact: true });
  const label = (name) => page.getByLabel(name, { exact: false });
  async function fresh(tab) {
    state.loggedIn = true; state.finalized = false;
    await page.setViewportSize({ width: 1440, height: 1050 });
    await page.goto('http://teacher:3001'); await button('Qo‘llanma').waitFor();
    if (tab) await button(tab).click();
  }
  async function shot(name, locators) {
    const modal = page.getByRole('dialog'); const inModal = await modal.count() > 0;
    if (inModal) await page.setViewportSize({ width: 1440, height: 1800 });
    for (const locator of locators) await locator.waitFor();
    await page.waitForTimeout(150); await annotate(page, locators);
    const box = inModal ? await modal.locator(':scope > div').boundingBox() : null;
    await page.screenshot({ path: `${target}/teacher-${name}.png`, ...(box ? { clip: { x: box.x - 8, y: box.y - 8, width: box.width + 16, height: box.height + 16 } } : { fullPage: true }) });
    await clearAnnotations(page); assert.deepEqual(errors, []);
    console.log(`Captured synthetic teacher-${name}: ${locators.length} numbered steps`);
  }
  await page.goto('http://teacher:3001');
  await label('Foydalanuvchi nomi').fill('namuna_teacher');
  await shot('login', [label('Foydalanuvchi nomi'), label('Parol').first(), button('Kirish')]);
  await label('Parol').first().fill('synthetic-only-example'); await button('Kirish').click();
  await shot('otp', [label('Tasdiqlash kodi'), page.getByText(/0[23]:[0-5][0-9]/).first(), button('Tasdiqlash')]);
  await fresh();
  await shot('groups', [page.getByText('English A', { exact: true }), button('O‘quvchilar').last(), button('Davomat').last()]);
  await button('O‘quvchilar').last().click();
  await button('Batafsil').first().click();
  await shot('students', [page.getByRole('dialog').getByRole('heading', { name: 'Namuna O‘quvchi', exact: true }), page.getByRole('dialog').getByText('Ota-ona ma’lumotlari', { exact: true }), label('Oy tanlash')]);
  await fresh();
  await page.locator('header').getByRole('button', { name: /Profilim/ }).click();
  await shot('profile', [page.getByText('Rasm yuklash', { exact: true }), label('Foydalanuvchi nomi (login)'), button('Saqlash')]);
  await fresh(); await button('Parol').click();
  await shot('password', [label('Joriy parol'), label('Yangi parol').first(), button('O‘zgartirish')]);
  await fresh('Davomat olish');
  await label('Dars sanasi').fill('2026-10-12');
  await shot('draft', [label('Guruhni tanlang').locator('..').locator('..'), page.getByRole('table'), button('Qoralama saqlash'), button('Davomatni yakunlash')]);
  await button('Davomatni yakunlash').click();
  await shot('finalize', [page.getByRole('dialog').getByText('Keldi', { exact: true }).locator('..').locator('..'), page.getByRole('dialog').getByText(/Telegram/).first(), button('Tasdiqlash va yakunlash')]);
  await fresh('Davomat olish');
  state.finalized = true; await page.reload(); await button('Davomat olish').click();
  await label('Dars sanasi').fill('2026-10-12');
  await button('Kech qoldi').click();
  await page.getByPlaceholder(/Izoh yozish/).fill('5 daqiqa kechikdi');
  await shot('correction', [page.getByText('Davomatni tahrirlash mumkin', { exact: true }).locator('..'), page.getByRole('table'), button('Tuzatishni saqlash')]);
  await button('O‘zgarishlar tarixi').click();
  await shot('audit', [label('Dars sanasi'), button('Tarixni yopish'), page.getByRole('table').last()]);
  await fresh('Davomat tarixi');
  await shot('history', [label('Guruhni tanlang'), page.locator('input[type="month"]'), page.getByRole('table')]);
  assert.deepEqual(unexpected, []); await browser.close();
  fs.writeFileSync('/workspace/.private/ui-acceptance/teacher-guide-capture.json', JSON.stringify({ synthetic: true, images: 11, no_live_api: true, numbered_markers: true, errors: [] }, null, 2), { mode: 0o600 });
})().catch(async (error) => {
  if (capturePage) await capturePage.screenshot({ path: '/workspace/.private/ui-acceptance/teacher-capture-failure.png', fullPage: true });
  console.error(error.message); process.exit(1);
});
