// Closed synthetic API fixtures; no real login, database writes or Telegram sends.
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const zlib = require('node:zlib');
const { user, teacher, ids, installFixtures } = require('./browser_fixtures.cjs');
const entry = { id: '12', at: '2026-10-14T07:00:01.123456Z', day: '2026-10-14',
  actor: { id: ids.teacher, name: 'Namuna Ustoz', username: 'namuna_ustoz', role: 'teacher' },
  action: 'attendance.correct', entity: { type: 'attendance', id: 'fixture-record', name: 'Namuna O‘quvchi' },
  changes: { status: { before: 'absent', after: 'present' }, note: { before: null, after: 'Aniqlashtirildi' } },
  private_changed: [], details: { reason: 'Jurnal qayta tekshirildi', group: { id: ids.group, name: 'English A' } },
  source: 'http', request_id: 'synthetic-request' };
const perms = ['staff:manage','subjects:manage','groups:read','groups:create','groups:edit','students:read','students:create','students:edit','attendance:read','attendance:write','messages:send'];
const httpEntry = { ...entry, id: '13', at: '2026-10-14T10:37:47.123456Z', action: 'http.request',
  actor: { id: ids.admin, name: 'Namuna Admin', username: 'sample_admin', role: 'superadmin' },
  entity: { type: null, id: null, name: null },
  changes: {}, details: { method: 'GET', route: '/api/v1/admin/dashboard/stats', status: 200, outcome: 'success' } };
(async () => {
  const browser = await chromium.launch({ headless: true });
  const output = '/workspace/.private/ui-acceptance/logs-110';
  fs.mkdirSync(output, { recursive: true, mode: 0o700 });
  for (const width of [1440, 768, 360]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, acceptDownloads: true });
    await context.addCookies([{ name: 'neoavlod_csrf', value: 'fixture-csrf', url: 'http://admin:3000' }]);
    const page = await context.newPage();
    const errors = []; page.on('pageerror', (error) => errors.push(error.message));
    const state = { user: { ...user, role: 'superadmin', permissions: [] } };
    const unexpected = await installFixtures(page, state);
    const calls = [];
    await page.route('**/api/v1/admin/logs**', async (route) => {
      const request = route.request(), url = new URL(request.url()); calls.push(url.pathname);
      assert.equal(request.method(), 'GET');
      if (url.pathname.endsWith('/download')) {
        assert.equal(request.headers()['x-csrf-token'], 'fixture-csrf');
        return route.fulfill({ contentType: 'application/gzip', body: zlib.gzipSync(JSON.stringify(entry)+'\n'),
          headers: { 'Content-Disposition': 'attachment; filename="neoavlod-logs-2026-10-14.jsonl.gz"' } });
      }
      if (url.pathname.endsWith('/days')) return route.fulfill({ json: [{ day: '2026-10-14', count: 1 }] });
      const rows = [entry, httpEntry].filter((row) => (!url.searchParams.get('actor_id') || row.actor.id === url.searchParams.get('actor_id')) &&
        (!url.searchParams.get('action') || row.action === url.searchParams.get('action')));
      return route.fulfill({ json: { items: rows, actors: [entry.actor, httpEntry.actor], actions: [entry.action, httpEntry.action], total: rows.length, next_cursor: null, page_size: 50 } });
    });
    await page.goto('http://admin:3000');
    if (width < 1024) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
    await page.getByRole('button', { name: 'Loglar', exact: true }).click();
    await page.getByRole('cell', { name: /Namuna Ustoz/ }).waitFor();
    await page.getByText('Admin paneli — Dashboard ko‘rsatkichlari olindi', { exact: true }).waitFor();
    await page.getByText('14.10.2026 15:37:47', { exact: true }).waitFor();
    assert.equal(await page.getByText('Paneldagi so‘rov', { exact: true }).count(), 0);
    await page.getByLabel('Log kuni').fill('2026-10-14');
    await page.getByLabel('Xodim', { exact: true }).selectOption(ids.teacher);
    await page.getByRole('cell', { name: /Namuna Ustoz/ }).waitFor();
    assert(await page.getByText(/12:00:01/).count());
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width} table overflow`);
    await page.screenshot({ path: `${output}/logs-${width}.png`, fullPage: true });
    await page.getByRole('button', { name: /Davomat tuzatildi tafsilotlari/ }).click();
    const dialog = page.getByRole('dialog', { name: 'Log tafsilotlari' });
    await dialog.getByText('Jurnal qayta tekshirildi').waitFor();
    assert.equal(await dialog.getByRole('button', { name: /O‘chirish|Tahrirlash/ }).count(), 0);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: `${output}/details-${width}.png`, fullPage: true });
    await page.keyboard.press('Escape');
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Kunlik logni yuklash' }).click();
    const download = await downloadPromise;
    await download.saveAs(`${output}/fixture-${width}.jsonl.gz`);
    assert.equal(download.suggestedFilename(), 'neoavlod-logs-2026-10-14.jsonl.gz');
    assert.equal(JSON.parse(zlib.gunzipSync(fs.readFileSync(`${output}/fixture-${width}.jsonl.gz`)).toString()).actor.name, 'Namuna Ustoz');
    assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
    await context.close();
    for (const role of ['admin', 'teacher']) {
      const limited = await browser.newPage({ viewport: { width, height: 1000 } });
      const who = role === 'teacher' ? teacher : { ...user, permissions: perms };
      await installFixtures(limited, { user: who });
      await limited.goto(role === 'teacher' ? 'http://teacher:3001' : 'http://admin:3000');
      if (width < 1024) await limited.getByRole('button', { name: 'Menyuni ochish' }).click();
      assert.equal(await limited.getByRole('button', { name: 'Loglar', exact: true }).count(), 0);
      await limited.getByRole('button', { name: role === 'teacher' ? 'Davomat olish' : 'Davomat', exact: true }).click();
      await limited.getByRole('button', { name: 'Kelmadi', exact: true }).waitFor();
      assert.equal(await limited.getByRole('button', { name: 'Audit tarixi', exact: true }).count(), 0);
      assert.equal(await limited.getByRole('button', { name: 'O‘zgarishlar tarixi', exact: true }).count(), 0);
      await limited.getByRole('button', { name: 'Kelmadi', exact: true }).click();
      await limited.getByRole('button', { name: 'Qoralama saqlash', exact: true }).click();
      await limited.getByText('Davomat tuzatish sababini kiritish shart', { exact: true }).waitFor();
      await limited.getByLabel('Tuzatish sababi', { exact: false }).fill('Namuna jurnal qayta tekshirildi');
      const saved = limited.waitForRequest((request) => request.url().endsWith('/attendance/draft') && request.method() === 'POST');
      await limited.getByRole('button', { name: 'Qoralama saqlash', exact: true }).click();
      assert.equal((await saved).postDataJSON().reason, 'Namuna jurnal qayta tekshirildi');
      await limited.getByText('Davomat qoralamasi muvaffaqiyatli saqlandi.', { exact: true }).waitFor();
      assert(await limited.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await limited.close();
    }
  }
  await browser.close();
  console.log('Logs UI: superadmin view/filter/seconds/diffs/reason/gzip download/CSRF; admin and teacher hidden;1440/768/360 no overflow or JS errors. Synthetic only.');
})().catch((error) => { console.error(error.message); process.exit(1); });
