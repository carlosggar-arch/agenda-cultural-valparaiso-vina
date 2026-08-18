import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const read = (relative) => fs.readFileSync(path.join(app, relative), "utf8");

const community = read("community-source.js");
const css = read("community-source.css");
const participation = read("participation-footer.js");
const appJs = read("app.js");
const pwa = read("pwa.js");
const worker = read("service-worker.js");
const release = read("release-version.js");

for (const marker of ["+ Aportar fuente", "Comentarios", "data-community-like", "FEEDBACK_API", "/likes", "/comments"]) {
  assert.match(community, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
}
assert.match(community, /community-source\.css\?v=20260818-feedback2/);
assert.match(appJs, /participation-footer\.js\?v=20260818-feedback4/);
assert.match(pwa, /community-source\.js\?v=20260818-feedback2/);
assert.match(pwa, /participation-footer\.js\?v=20260818-feedback4/);
assert.match(worker, /community-source\.js\?v=20260818-feedback2/);
assert.match(worker, /community-source\.css\?v=20260818-feedback2/);
assert.match(worker, /participation-footer\.js\?v=20260818-feedback4/);
assert.match(worker, /pwa\.js\?v=20260818-feedback4/);
assert.match(css, /\.source-proposal-actions\{[^}]*flex-wrap:nowrap/s);
assert.match(participation, /vivamos-participation-rail/);
assert.match(participation, /data-sources-toggle/);
assert.match(participation, /sourceCta\.hidden = true/);
assert.match(participation, /display:flex !important/);
assert.match(participation, /flex-wrap:nowrap !important/);
assert.match(participation, /overflow-x:auto/);
assert.doesNotMatch(participation, /grid-column:\s*1\s*\/\s*-1/);
assert.doesNotMatch(participation, /MutationObserver|IntersectionObserver|addEventListener\(["']scroll/);
assert.match(release, /const RELEASE = 100/);

console.log("Public feedback visible in the original footer action row for WEB + PWA: OK");
