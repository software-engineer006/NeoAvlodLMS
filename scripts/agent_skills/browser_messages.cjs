// Actual app DOM with synthetic API responses. No request reaches Telegram or the database.
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { annotate, clearAnnotations } = require('./browser_helpers.cjs');
const zero = { pending: 0, delivered: 0, failed: 0, skipped: 0, cancelled: 0 };
const user = { id: 'fixture-admin', username: 'namuna_admin', first_name: 'Namuna', last_name: 'Administrator', phone: null,
  status: 'active', role: 'admin', permissions: ['messages:send'] };
const recipient = { id: 'fixture-parent', kind: 'parent', name: 'Namuna ota-ona', group_names: ['English A'],
  student_names: ['Namuna o‘quvchi'], connected: true, connection_reason: null };
(async () => {
  const browser = await chromium.launch({ headless: true });
  fs.mkdirSync('/workspace/.private/ui-acceptance', { recursive: true, mode: 0o700 });
  for (const width of [1440, 768, 360]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 } });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('**/api/**', async (route) => {
      const url = new URL(route.request().url());
      if (!url.pathname.startsWith('/api/')) return route.continue();
      let body;
      if (url.pathname.endsWith('/me')) body = user;
      else if (url.pathname.endsWith('/messages/groups')) body = [{ id: 'fixture-group', name: 'English A', students: 3 }];
      else if (url.pathname.endsWith('/recipients')) body = { items: [recipient], total: 1, page: 1, page_size: 25 };
      else if (url.pathname.endsWith('/preview')) {
        const draft = route.request().postDataJSON();
        body = { digest: 'a'.repeat(64), message: `NeoAvlod LMS\n\n${draft.title}\n\n${draft.body}`, bot_configured: true,
          total: 3, eligible: 2, unlinked: 1, duplicates: 0, parents: 3, students: 0, sample: [recipient] };
      } else if (url.pathname.endsWith('/messages')) body = { items: [], total: 0, page: 1, page_size: 10, summary: zero };
      else if (url.pathname.endsWith('/health')) body = { status: 'ok', database: 'ok' };
      else if (url.pathname.endsWith('/stats')) body = { staff_count: null, staff_breakdown: null, groups_count: null, students_count: null };
      else return route.fulfill({ status: 403, json: { detail: 'Synthetic permission boundary' } });
      await route.fulfill({ json: body });
    });
    await page.goto('http://admin:3000');
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `/workspace/.private/ui-acceptance/messages-initial-${width}.png`, fullPage: true });
    if (errors.length) throw new Error(errors.join('\n'));
    if (width < 1024) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
    await page.getByRole('button', { name: 'Xabarlar', exact: true }).click();
    await page.getByRole('button', { name: /Barchaga/ }).click();
    await page.getByLabel('Xabar sarlavhasi', { exact: false }).fill('Dars haqida eslatma');
    await page.getByLabel('Xabar matni', { exact: false }).fill('English A guruhi: navbatdagi dars soat 09:00 da boshlanadi.');
    await page.getByRole('button', { name: 'Qabul qiluvchilarni ko‘rib chiqish' }).click();
    await page.getByRole('button', { name: 'Yuborishni tasdiqlash' }).waitFor();
    assert.equal(await page.getByText('Amal bajarilmadi', { exact: true }).count(), 0);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}px horizontal overflow`);
    await page.screenshot({ path: `/workspace/.private/ui-acceptance/messages-${width}.png`, fullPage: true });
    if (width === 1440) {
      await annotate(page, [page.getByRole('button', { name: /Barchaga/ }), page.getByLabel('Xabar sarlavhasi', { exact: false }),
        page.getByLabel('Xabar matni', { exact: false }), page.getByRole('button', { name: 'Yuborishni tasdiqlash' })]);
      await page.screenshot({ path: '/workspace/.private/ui-acceptance/messages-annotated.png', fullPage: true });
      await clearAnnotations(page);
    }
    await page.getByRole('button', { name: 'Yuborishni tasdiqlash' }).click();
    const dialog = page.getByRole('dialog', { name: 'Xabar yuborishni tasdiqlash' });
    await dialog.waitFor();
    assert(await dialog.getByRole('button', { name: 'Navbatga qo‘shish' }).isEnabled());
    const lastButton = dialog.getByRole('button', { name: 'Navbatga qo‘shish' });
    await lastButton.focus(); await page.keyboard.press('Tab');
    assert(await dialog.getByRole('button', { name: 'Yopish', exact: true }).evaluate((node) => node === document.activeElement));
    await page.screenshot({ path: `/workspace/.private/ui-acceptance/messages-confirm-${width}.png`, fullPage: true });
    assert.deepEqual(errors, []);
    await page.close();
  }
  await browser.close();
  console.log('Message app browser flow: 1440/768/360, confirmation, no overflow or JS errors; synthetic only.');
})().catch((error) => { console.error(error.message); process.exit(1); });
