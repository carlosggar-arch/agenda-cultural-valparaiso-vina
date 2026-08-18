import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const read = (relative) => fs.readFileSync(path.join(app, relative), "utf8");

const community = read("community-source.js");
const participation = read("participation-footer.js");
const webActions = read("web-actions-below-mosaic.js");
const actionLayout = read("action-strip-layout.js");
const installedMosaic = read("installed-mosaic.js");
const appJs = read("app.js");
const pwa = read("pwa.js");
const worker = read("service-worker.js");
const release = read("release-version.js");

for (const marker of ["Comentarios", "data-community-like", "FEEDBACK_API", "/likes", "/comments", "LIKE_PENDING_KEY", "syncPendingLike"]) {
  assert.match(community, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
}
assert.match(community, /data-like-count>0/);
assert.match(community, /storageSet\(LIKED_KEY, "1"\)/);
assert.match(participation, /mountHeaderFeedback/);
assert.match(participation, /\.header-actions/);
assert.match(participation, /data-contribute-source/);
assert.match(participation, /insertAdjacentElement\("afterend", comments\)/);
assert.match(participation, /insertAdjacentElement\("afterend", like\)/);
assert.match(participation, /restoreFooterContact/);
assert.match(participation, /display: flex !important/);
assert.match(participation, /overflow-x: auto !important/);
assert.doesNotMatch(participation, /IntersectionObserver|addEventListener\(["']scroll/);

assert.match(webActions, /display: flex !important/);
assert.match(webActions, /overflow-x: auto !important/);
assert.doesNotMatch(webActions, /MutationObserver/);
assert.doesNotMatch(webActions, /grid-template-columns: repeat\(auto-fit/);

assert.match(actionLayout, /background: transparent !important/);
assert.match(actionLayout, /border: 0 !important/);
assert.match(actionLayout, /padding: 0 !important/);
assert.match(actionLayout, /flex-basis: 0 !important/);
assert.match(actionLayout, /flex: 1\.75 1 0 !important/);
assert.match(actionLayout, /flex: 1\.25 1 0 !important/);
assert.match(actionLayout, /flex: \.62 1 0 !important/);
assert.doesNotMatch(actionLayout, /MutationObserver|IntersectionObserver|addEventListener\(["']scroll/);

assert.match(installedMosaic, /grid-template-columns: repeat\(7, minmax\(0, 1fr\)\) !important/);
assert.match(installedMosaic, /grid-template-rows: 1fr !important/);
assert.match(installedMosaic, /data-community-comments/);
assert.match(installedMosaic, /data-community-like/);
assert.doesNotMatch(installedMosaic, /grid-template-columns: repeat\(5/);

assert.match(appJs, /community-source\.js\?v=20260818-feedback3/);
assert.match(appJs, /participation-footer\.js\?v=20260818-feedback6/);
assert.match(pwa, /community-source\.js\?v=20260818-feedback3/);
assert.match(pwa, /participation-footer\.js\?v=20260818-feedback6/);
assert.match(pwa, /installed-mosaic\.js\?v=20260818-f12-dual3/);
assert.match(pwa, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(pwa, /action-strip-layout\.js\?v=20260818-fill1/);
assert.match(worker, /community-source\.js\?v=20260818-feedback3/);
assert.match(worker, /participation-footer\.js\?v=20260818-feedback6/);
assert.match(worker, /installed-mosaic\.js\?v=20260818-f12-dual3/);
assert.match(worker, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(worker, /action-strip-layout\.js\?v=20260818-fill1/);
assert.match(worker, /pwa\.js\?v=20260818-feedback6/);
assert.match(release, /const RELEASE = 106/);

console.log("Public feedback: WEB strip preserved and installed mobile actions stay on one row: OK");
