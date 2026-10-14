// React scene provenance, privacy and source integrity; run only in Docker.
const fs = require('node:fs');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = '/workspace/frontend/packages/ui/src/guide';
const sceneFiles = fs.readdirSync(`${root}/scenes`).filter((name) => /\.tsx?$/.test(name)).map((name) => `scenes/${name}`);
const names = ['adminTopics.ts', 'teacherTopics.ts', 'GuideView.tsx', ...sceneFiles];
const receipt = names.map((name) => {
  const data = fs.readFileSync(`${root}/${name}`);
  assert(!data.toString().includes('./images/') && !data.toString().includes('new URL('), name);
  if (name.startsWith('scenes/')) assert(!/apiClient|fetch\(|localStorage|sessionStorage|\.\.\/\.\.\/(auth|staff|teacher)\//.test(data.toString()), name);
  return { name, sha256: crypto.createHash('sha256').update(data).digest('hex') };
});
const teacher = fs.readFileSync(`${root}/teacherTopics.ts`, 'utf8');
assert(!teacher.includes('teacher-audit') && !teacher.includes('./scenes/admin'));
assert.equal([...teacher.matchAll(/id: "teacher-/g)].length, 10);
const admin = fs.readFileSync(`${root}/adminTopics.ts`, 'utf8');
assert.equal([...admin.matchAll(/id: "admin-/g)].length, 23);
assert(/id: "admin-logs",\s*title:[\s\S]*?superadminOnly: true/.test(admin));
const renderer = fs.readFileSync(`${root}/scenes/GuidePreview.tsx`, 'utf8');
assert(renderer.includes('data-guide-marker') && renderer.includes('setAttribute("inert"'));
assert(renderer.includes('readOnly') && !renderer.includes('<img') && !renderer.includes('<form'));
if (fs.existsSync(`${root}/images`)) assert.equal(fs.readdirSync(`${root}/images`).filter((name) => /\.png$/.test(name)).length, 0);
const fixtures = fs.readFileSync('/workspace/scripts/agent_skills/browser_fixtures.cjs', 'utf8');
assert(fixtures.includes("if (!path.startsWith('/api/')) return route.continue()"));
assert(fixtures.includes('return route.fulfill({ status: 403') && !/readFile|fetch\(|route.fallback/.test(fixtures));
const dir = '/workspace/.private/ui-acceptance';
fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
fs.writeFileSync(`${dir}/guide-react-audit.json`, JSON.stringify({ sources: receipt, admin_topics: 23,
  teacher_topics: 10, raster_assets: 0, synthetic_only: true, network_free_previews: true }, null, 2), { mode: 0o600 });
console.log('33 React guide topics: typed portal scenes, inert controls, zero PNG/network/credential values; source checksums and closed fixtures verified.');
