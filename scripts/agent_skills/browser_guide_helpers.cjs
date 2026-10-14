const assert = require('node:assert/strict');
async function verifyPreview(page) {
  const article = page.getByRole('article');
  const preview = article.locator('[data-guide-preview]');
  await preview.waitFor();
  assert(await preview.getAttribute('aria-label'));
  assert.equal(await article.locator('img').count(), 0);
  const markers = await preview.locator('[data-guide-marker]').evaluateAll((nodes) => nodes.map((node) => Number(node.dataset.guideMarker)));
  const steps = await article.getByRole('list', { name: 'Amaliy qadamlar' }).locator('li').count();
  assert.deepEqual(markers, Array.from({ length: steps }, (_, i) => i + 1));
  assert(await preview.locator('[inert]').evaluate((node) => node.inert));
  for (const control of await preview.locator('input,select,button').all()) {
    assert.equal(await control.getAttribute('tabindex'), '-1');
    assert(await control.evaluate((node) => { node.focus(); return document.activeElement !== node; }));
  }
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
}
async function verifyZoom(page) {
  await page.getByRole('button', { name: /Namunani kattalashtirish/ }).click();
  const dialog = page.getByRole('dialog'); await dialog.waitFor();
  assert.equal(await dialog.locator('img').count(), 0);
  assert(await dialog.locator('[inert]').evaluate((node) => node.inert));
  const input = dialog.locator('input,select').first();
  if (await input.count()) assert(await input.evaluate((node) => parseFloat(getComputedStyle(node).fontSize) >= 16));
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'hidden' });
}
module.exports = { verifyPreview, verifyZoom };
