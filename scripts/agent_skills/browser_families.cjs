// Closed synthetic family fixtures; no live writes, login or messages.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { user, student, parent, ids, installFixtures } = require('./browser_fixtures.cjs');
const { verifyPreview } = require('./browser_guide_helpers.cjs');
(async () => {
  const browser = await chromium.launch(), output = '/workspace/.private/families-128/ui';
  fs.mkdirSync(output, { recursive: true, mode: 0o700 });
  for (const width of [1440, 768, 360]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'Asia/Tashkent' });
    page.setDefaultTimeout(10000);
    const writes = [], errors = [], state = { user: { ...user, role: 'superadmin' } };
    page.on('pageerror', error => errors.push(error.message));
    const unexpected = await installFixtures(page, state);
    let pupil = { ...student, parent: { ...parent, child_count: 2 } };
    const otherParent = { ...parent, id: '00000000-0000-4000-8000-000000000201', first_name: 'Boshqa', child_count: 1 };
    await page.route('**/api/v1/**', async route => {
      const request = route.request(), path = new URL(request.url()).pathname;
      if (path.endsWith('/lookups/parents')) return route.fulfill({ json: { items: [pupil.parent, otherParent] } });
      if (path === '/api/v1/admin/students') return route.fulfill({ json: { items: [pupil], total: 1, page: 1, page_size: 10 } });
      if (path === `/api/v1/admin/students/${ids.student}`) {
        if (request.method() === 'PATCH') {
          const body = request.postDataJSON(); writes.push(body);
          pupil = { ...pupil, ...body, parent_id: body.parent_id, parent: body.parent_id ? otherParent : null };
        }
        return route.fulfill({ json: pupil });
      }
      return route.fallback();
    });
    async function nav(name) {
      const button = page.getByRole('button', { name, exact: true });
      if (!await button.isVisible()) await page.getByRole('button', { name: 'Menyuni ochish' }).click(); await button.click();
    }
    await page.goto('http://admin:3000'); await nav('O‘quvchilar');
    await page.getByText('Namuna O‘quvchi', { exact: true }).click();
    await page.getByRole('dialog').getByText(/Bu ota-onaga 2 ta bola bog‘langan/).waitFor();
    await page.keyboard.press('Escape'); await page.getByTitle('Tahrirlash').click();
    const dialog = page.getByRole('dialog');
    await dialog.getByText(/Bu ota-onaga 2 ta bola bog‘langan/).waitFor();
    await dialog.getByLabel('Ota-onani bog‘lash').selectOption('existing');
    await dialog.getByRole('option', { name: /Boshqa/ }).waitFor({ state: 'attached' });
    await dialog.getByLabel('Mavjud ota-ona', { exact: true }).selectOption(otherParent.id);
    await dialog.getByRole('button', { name: 'Saqlash', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' }); assert.equal(writes[0].parent_id, otherParent.id); assert(!writes[0].parent);
    await page.getByText('Namuna O‘quvchi', { exact: true }).click();
    await dialog.getByText('Boshqa Ota-ona', { exact: true }).waitFor();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: `${output}/family-${width}.png`, fullPage: true });
    await page.keyboard.press('Escape'); await nav('Qo‘llanma');
    await page.getByLabel('Qo‘llanmadan qidirish').fill('O‘quvchi va ota-onani qo‘shish');
    await page.getByRole('navigation', { name: 'Qo‘llanma mavzulari' }).getByRole('button').click(); await verifyPreview(page);
    assert.deepEqual(unexpected, []); assert.deepEqual(errors, []); await page.close();
  }
  await browser.close(); console.log('Family UI: shared count/warning, explicit existing parent selection, no cloned parent body, native guide,1440/768/360; closed fixtures.');
})().catch(error => { console.error(error.stack); process.exit(1); });
