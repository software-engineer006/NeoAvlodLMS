import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const excluded = new Set(["node_modules", "dist", "release", ".git"]);
function files(dir) {
  return readdirSync(dir).sort().flatMap((name) => {
    if (excluded.has(name) || name.startsWith(".env") || name.endsWith(".tsbuildinfo")) return [];
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return [path];
  });
}
const hash = (data) => createHash("sha256").update(data).digest("hex");
const source = createHash("sha256");
for (const path of files(root)) source.update(relative(root, path)).update("\0").update(readFileSync(path)).update("\0");
const sourceDigest = source.digest("hex");
function assetHashes(dir) {
  const walk = (folder) => readdirSync(folder).sort().flatMap((name) => {
    const path = join(folder, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
  return Object.fromEntries(walk(dir).map((path) => [relative(dir, path).replaceAll("\\", "/"), hash(readFileSync(path))]));
}
const release = join(root, "release");
const check = process.argv.includes("--check");
if (!check) {
  rmSync(release, { recursive: true, force: true });
  mkdirSync(release, { recursive: true });
  for (const app of ["admin", "teacher"]) {
    const dist = join(root, "apps", app, "dist");
    if (!existsSync(join(dist, "index.html"))) throw new Error(`Missing ${app} build`);
    cpSync(dist, join(release, app), { recursive: true });
  }
  writeFileSync(join(release, "manifest.json"), JSON.stringify({ schema: 1, source_sha256: sourceDigest, assets: {
    admin: assetHashes(join(release, "admin")), teacher: assetHashes(join(release, "teacher")),
  } }, null, 2) + "\n");
} else {
  const manifest = JSON.parse(readFileSync(join(release, "manifest.json"), "utf8"));
  if (manifest.schema !== 1 || manifest.source_sha256 !== sourceDigest) throw new Error("Frontend release is stale. Run scripts/deploy/build_frontend.sh and commit frontend/release.");
  for (const app of ["admin", "teacher"]) {
    const expected = JSON.stringify(manifest.assets[app]);
    if (JSON.stringify(assetHashes(join(release, app))) !== expected) throw new Error(`${app} committed release modified`);
    if (JSON.stringify(assetHashes(join(root, "apps", app, "dist"))) !== expected) throw new Error(`${app} release differs from clean CI build`);
  }
}
console.log(check ? "Frontend source, committed assets and clean build match." : "Production frontend/release ready to commit.");
