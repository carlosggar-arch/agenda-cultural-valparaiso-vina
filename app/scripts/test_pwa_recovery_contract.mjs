import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const release = fs.readFileSync(path.join(app, "release-version.js"), "utf8");
const pwa = fs.readFileSync(path.join(app, "pwa.js"), "utf8");

assert.match(release, /const RELEASE = 81/);
assert.match(release, /MIN_SAFE_SERVICE_WORKER_RELEASE = 81/);
assert.match(release, /navigator\.serviceWorker\.controller/);
assert.match(release, /getRegistrations\(\)/);
assert.match(release, /registration\.unregister\(\)/);
assert.match(release, /name\.startsWith\("agenda-cultural-"\)/);
assert.match(release, /caches\.delete\(name\)/);
assert.match(release, /window\.stop\(\)/);
assert.match(release, /pwa_recovered/);
assert.match(pwa, /service-worker\.js\?v=\$\{APP_RELEASE\}/);
assert.match(pwa, /updateViaCache:\s*"none"/);

console.log("PWA stale-worker recovery contract: OK");
