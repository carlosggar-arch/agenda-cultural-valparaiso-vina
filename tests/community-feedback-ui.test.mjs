import assert from "node:assert/strict";
import fs from "node:fs";

const js = fs.readFileSync(new URL("../app/community-source.js", import.meta.url), "utf8");
const css = fs.readFileSync(new URL("../app/community-source.css", import.meta.url), "utf8");
const participation = fs.readFileSync(new URL("../app/participation-footer.js", import.meta.url), "utf8");
const app = fs.readFileSync(new URL("../app/app.js", import.meta.url), "utf8");
const pwa = fs.readFileSync(new URL("../app/pwa.js", import.meta.url), "utf8");
const worker = fs.readFileSync(new URL("../app/service-worker.js", import.meta.url), "utf8");
const release = fs.readFileSync(new URL("../app/release-version.js", import.meta.url), "utf8");

assert.match(js, /data-source-proposal-link/);
assert.match(js, /data-community-comments/);
assert.match(js, /data-community-like/);
assert.match(js, /community\/v1\/feedback/);
assert.match(js, /vivamos-global-like-token-v1/);
assert.match(js, /pending_review/);
assert.match(js, /Comentario recibido/);
assert.match(css, /\.source-proposal-actions\{[^}]*display:flex[^}]*flex-wrap:nowrap/s);
assert.match(participation, /vivamos-participation-rail/);
assert.match(participation, /sourceCta\.hidden = true/);
assert.match(participation, /data-sources-toggle/);
assert.match(participation, /flex-wrap:\s*nowrap/);
assert.match(participation, /overflow-x:\s*auto/);
assert.doesNotMatch(participation, /MutationObserver|IntersectionObserver|addEventListener\(["']scroll/);
assert.match(app, /community-source\.js\?v=20260818-feedback2/);
assert.match(app, /participation-footer\.js\?v=20260818-feedback3/);
assert.match(pwa, /community-source\.js\?v=20260818-feedback2/);
assert.match(pwa, /participation-footer\.js\?v=20260818-feedback3/);
assert.match(worker, /participation-footer\.js\?v=20260818-feedback3/);
assert.match(worker, /pwa\.js\?v=20260818-feedback3/);
assert.match(release, /const RELEASE = 99/);

console.log("Community feedback UI contract: visible single footer rail in WEB + PWA");
