const fs = require('node:fs');
const assert = require('node:assert/strict');
for (const [portal, own, foreign, count] of [['admin', 'admin-', 'teacher-', 21], ['teacher', 'teacher-', 'admin-', 11]]) {
  const folder = `/workspace/frontend/release/${portal}/assets`;
  const files = fs.readdirSync(folder);
  assert.equal(files.filter((name) => name.startsWith(own) && name.endsWith('.png')).length, count);
  assert.equal(files.filter((name) => name.startsWith(foreign)).length, 0, `${portal} includes other portal images`);
  const code = files.filter((name) => name.endsWith('.js')).map((name) => fs.readFileSync(`${folder}/${name}`, 'utf8')).join('\n');
  assert(code.includes('Qo‘llanma'));
  if (portal === 'teacher') {
    assert(!code.includes('Administrator va barcha ruxsatlar'));
    assert(!code.includes('admin-grants-'));
  }
}
console.log('Guide release assets are portal-scoped:admin21/teacher11;teacher contains no administrator grant/bot manual.');
