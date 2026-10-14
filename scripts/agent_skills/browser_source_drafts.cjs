// Synthetic source-draft visibility and selected-course profile context.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { user, teacher, group, student, ids, installFixtures } = require('./browser_fixtures.cjs');
(async () => {
  const browser = await chromium.launch();
  const production = process.argv.includes('--production');
  const output = `/workspace/.private/refresh-132/ui/${production ? 'production' : 'local'}`;
  fs.mkdirSync(output, { recursive: true, mode: 0o700 });
  for (const width of [1440, 768, 360]) for (const portal of ['admin', 'teacher']) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'Asia/Tashkent' });
    const errors = [], calls = [];
    page.on('pageerror', error => errors.push(error.message));
    const unexpected = await installFixtures(page, { user: portal === 'admin' ? { ...user, role: 'superadmin' } : teacher });
    await page.route('**/api/v1/**', async route => {
      const url = new URL(route.request().url()), path = url.pathname;
      if (path.endsWith('attendance/history')) {
        const month = url.searchParams.get('month') || '2026-10', day = `${month}-14`;
        return route.fulfill({ json: { group_id: ids.group, group_name: group.name, month, dates: [day],
          records: [{ attendance_id: 'source-fixture', student_id: ids.student, student_name: 'Namuna O‘quvchi', date: day, status: 'present', note: null, source_imported: true }],
          students_summary: [{ student_id: ids.student, student_name: 'Namuna O‘quvchi', present_count: 1, absent_count: 0, late_count: 0, attended_count: 1, total_lessons: 1 }],
          summary: { total_lessons: 1, total_records: 1, present_count: 1, late_count: 0, absent_count: 0 } } });
      }
      if (path === `/api/v1/teacher/students/${ids.student}`) {
        calls.push(url.searchParams.get('group_id'));
        return route.fulfill({ json: { ...student, group_name: group.name, subject_name: 'English', teacher_name: 'Namuna Ustoz' } });
      }
      return route.fallback();
    });
    await page.goto(production ? `https://${portal}.eduneo.uz` : `http://${portal}:${portal === 'admin' ? 3000 : 3001}`);
    const name = portal === 'admin' ? 'Davomat' : 'Davomat tarixi';
    if (width < 1024) await page.getByRole('button', { name: 'Menyuni ochish' }).click();
    await page.getByRole('button', { name, exact: true }).click();
    if (portal === 'admin') await page.getByRole('button', { name: 'Oylik jadval (Guruh / Oy)', exact: true }).click();
    await page.getByText(/CSVdagi aniq «k» belgilar ham ko‘rsatilgan/).waitFor();
    await page.getByText('Namuna O‘quvchi', { exact: true }).first().waitFor();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: `${output}/${portal}-source-${width}.png`, fullPage: true });
    if (portal === 'teacher') {
      await page.getByRole('button', { name: 'Namuna O‘quvchi', exact: true }).click();
      await page.getByRole('dialog').waitFor(); assert.equal(calls.at(-1), ids.group);
    }
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []); await page.close();
  }
  await browser.close(); console.log('Source-draft history clearly labelled, no absence inference, teacher selected-course profile,1440/768/360; closed fixtures passed.');
})().catch(error => { console.error(error.stack); process.exit(1); });
