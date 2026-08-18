import assert from "node:assert/strict";
import fs from "node:fs";

const js = fs.readFileSync(new URL("../app/community-source.js", import.meta.url), "utf8");
const participation = fs.readFileSync(new URL("../app/participation-footer.js", import.meta.url), "utf8");
const webActions = fs.readFileSync(new URL("../app/web-actions-below-mosaic.js", import.meta.url), "utf8");
const actionLayout = fs.readFileSync(new URL("../app/action-strip-layout.js", import.meta.url), "utf8");
const installedMosaic = fs.readFileSync(new URL("../app/installed-mosaic.js", import.meta.url), "utf8");
const app = fs.readFileSync(new URL("../app/app.js", import.meta.url), "utf8");
const pwa = fs.readFileSync(new URL("../app/pwa.js", import.meta.url), "utf8");
const worker = fs.readFileSync(new URL("../app/service-worker.js", import.meta.url), "utf8");
const release = fs.readFileSync(new URL("../app/release-version.js", import.meta.url), "utf8");

assert.match(js, /data-community-comments/);
assert.match(js, /data-community-like/);
assert.match(js, /community\/v1\/feedback/);
assert.match(js, /vivamos-global-like-token-v1/);
assert.match(js, /vivamos-global-like-pending-v1/);
assert.match(js, /storageSet\(LIKED_KEY, "1"\)/);
assert.match(js, /storageSet\(LIKE_PENDING_KEY, "1"\)/);
assert.match(js, /syncPendingLike/);
assert.match(js, /data-like-count>0/);

assert.match(participation, /mountHeaderFeedback/);
assert.match(participation, /document\.querySelector\("\.header-actions"\)/);
assert.match(participation, /data-contribute-source/);
assert.match(participation, /contribute\.insertAdjacentElement\("afterend", comments\)/);
assert.match(participation, /comments\.insertAdjacentElement\("afterend", like\)/);
assert.match(participation, /display: flex !important/);
assert.match(participation, /overflow-x: auto !important/);
assert.match(participation, /restoreFooterContact/);
assert.doesNotMatch(participation, /MutationObserver|IntersectionObserver|addEventListener\(["']scroll/);

assert.match(webActions, /display: flex !important/);
assert.match(webActions, /overflow-x: auto !important/);
assert.doesNotMatch(webActions, /MutationObserver/);
assert.doesNotMatch(webActions, /grid-template-columns: repeat\(auto-fit/);

assert.match(actionLayout, /background: transparent !important/);
assert.match(actionLayout, /border: 0 !important/);
assert.match(actionLayout, /padding: 0 !important/);
assert.match(actionLayout, /@media \(min-width: 701px\)/);
assert.match(actionLayout, /flex-basis: 0 !important/);
assert.match(actionLayout, /\.favorites-access--app[\s\S]*flex: 1\.15 1 0 !important/);
assert.match(actionLayout, /\.header-search-toggle[\s\S]*flex: \.52 1 0 !important/);
assert.match(actionLayout, /\.city-switch[\s\S]*flex: 1\.75 1 0 !important/);
assert.match(actionLayout, /\.contribute-source-button[\s\S]*flex: 1\.25 1 0 !important/);
assert.match(actionLayout, /\.source-feedback-button[\s\S]*flex: 1\.12 1 0 !important/);
assert.match(actionLayout, /\.source-like-button[\s\S]*flex: \.62 1 0 !important/);
assert.doesNotMatch(actionLayout, /MutationObserver|IntersectionObserver|addEventListener\(["']scroll/);

// Installed mobile PWA must keep all seven controls on exactly one continuous row.
assert.match(installedMosaic, /grid-template-columns: repeat\(7, minmax\(0, 1fr\)\) !important/);
assert.match(installedMosaic, /grid-template-rows: 1fr !important/);
assert.match(installedMosaic, /gap: 0 !important/);
assert.match(installedMosaic, /column-gap: 0 !important/);
assert.match(installedMosaic, /border-radius: 0 !important/);
assert.match(installedMosaic, /\* \+ \*[\s\S]*border-left-width: 0 !important/);
assert.match(installedMosaic, /data-community-comments/);
assert.match(installedMosaic, /data-community-like/);
assert.match(installedMosaic, /\[data-city-switch-label\]::after[\s\S]*content: "Ciudad"/);
assert.match(installedMosaic, /\[data-contribute-source\] > span:last-child/);
assert.match(installedMosaic, /overflow: hidden !important/);
assert.doesNotMatch(installedMosaic, /grid-template-columns: repeat\(5/);

assert.match(app, /community-source\.js\?v=20260818-feedback3/);
assert.match(app, /participation-footer\.js\?v=20260818-feedback6/);
assert.match(pwa, /community-source\.js\?v=20260818-feedback3/);
assert.match(pwa, /participation-footer\.js\?v=20260818-feedback6/);
assert.match(pwa, /installed-mosaic\.js\?v=20260818-f12-dual4/);
assert.match(pwa, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(pwa, /action-strip-layout\.js\?v=20260818-fill1/);
assert.match(worker, /community-source\.js\?v=20260818-feedback3/);
assert.match(worker, /participation-footer\.js\?v=20260818-feedback6/);
assert.match(worker, /installed-mosaic\.js\?v=20260818-f12-dual4/);
assert.match(worker, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(worker, /action-strip-layout\.js\?v=20260818-fill1/);
assert.match(worker, /pwa\.js\?v=20260818-feedback6/);
assert.match(release, /const RELEASE = 107/);

console.log("Community feedback UI contract: WEB proportional strip + installed mobile gapless seven-control row");
