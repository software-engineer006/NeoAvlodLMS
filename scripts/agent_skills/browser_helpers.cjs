// Numbered markers are rendered in the synthetic browser DOM before screenshotting.
// No real pupil data or existing raster image is edited.
async function annotate(page, locators) {
  await page.evaluate(() => document.querySelectorAll('[data-guide-marker]').forEach((node) => node.remove()));
  for (let index = 0; index < locators.length; index++) {
    const box = await locators[index].boundingBox();
    if (!box) throw new Error(`Guide marker ${index + 1} has no visible target`);
    await page.evaluate(({ box, number }) => {
      const marker = document.createElement('div');
      marker.setAttribute('data-guide-marker', 'true');
      marker.setAttribute('aria-hidden', 'true');
      Object.assign(marker.style, { position: 'absolute', zIndex: '100', pointerEvents: 'none',
        left: `${box.x + scrollX}px`, top: `${box.y + scrollY}px`, width: `${box.width}px`, height: `${box.height}px`,
        border: '2px solid #2563eb', borderRadius: '8px', boxShadow: '0 0 0 3px #dbeafe', boxSizing: 'border-box' });
      const label = document.createElement('span'); label.textContent = String(number);
      Object.assign(label.style, { position: 'absolute', top: box.width < 80 ? '-7px' : '-13px', left: box.width < 80 ? '-34px' : '8px', width: '27px', height: '27px',
        display: 'grid', placeItems: 'center', borderRadius: '50%', color: 'white', background: '#1d4ed8',
        font: 'bold 16px Inter, sans-serif', border: '2px solid white', boxShadow: '0 2px 4px #64748b' });
      marker.append(label); document.body.append(marker);
    }, { box, number: index + 1 });
  }
}
async function clearAnnotations(page) {
  await page.evaluate(() => document.querySelectorAll('[data-guide-marker]').forEach((node) => node.remove()));
}
module.exports = { annotate, clearAnnotations };
