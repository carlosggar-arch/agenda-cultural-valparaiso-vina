import assert from "node:assert/strict";
import fs from "node:fs";

const js = fs.readFileSync(new URL("../app/community-source.js", import.meta.url), "utf8");
const participation = fs.readFileSync(new URL("../app/participation-footer.js", import.meta.url), "utf8");
const webActions = fs.readFileSync(new URL("../app/web-actions-below-mosaic.js", import.meta.url), "utf8");
const actionLayout = fs.readFileSync(new URL("../app/action-strip-layout.js", import.meta.url), "utf8");
const installedMosaic = fs.readFileSync(new URL("../app/installed-mosaic.js", import.meta.url), "utf8");
const mobileSix = fs.readFileSync(new URL("../app/mobile-action-strip-six.js", import.meta.url), "utf8");
const shareQrCss = fs.readFileSync(new URL("../app/share-qr.css", import.meta.url), "utf8");
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

// Current public header contract: comments remain visible, the old like control
// is removed, and the installed mobile action strip is reduced to six actions.
assert.match(participation, /mountHeaderFeedback/);
assert.match(participation, /document\.querySelector\("\.header-actions"\)/);
assert.match(participation, /data-contribute-source/);
assert.match(participation, /contribute\.insertAdjacentElement\("afterend", comments\)/);
assert.match(participation, /querySelectorAll\("\[data-community-like\], \.source-like-button"\)\.forEach\(\(node\) => node\.remove\(\)\)/);
assert.match(participation, /grid-template-columns: repeat\(6, minmax\(0, 1fr\)\) !important/);
assert.match(participation, /restoreFooterContact/);
assert.doesNotMatch(participation, /comments\.insertAdjacentElement\("afterend", like\)/);
assert.doesNotMatch(participation, /MutationObserver|IntersectionObserver|addEventListener\(["']scroll/);

// The base WEB action module must already be correct on its own. Do not depend
// on a later optional enhancement to remove the white shell or distribute width.
assert.match(webActions, /display: flex !important/);
assert.match(webActions, /background: transparent !important/);
assert.match(webActions, /border: 0 !important/);
assert.match(webActions, /padding: 0 !important/);
assert.match(webActions, /flex-basis: 0 !important/);
assert.match(webActions, /flex: 1\.75 1 0 !important/);
assert.match(webActions, /flex: 1\.25 1 0 !important/);
assert.doesNotMatch(webActions, /background: rgba\(255,255,255,\.78\) !important/);
assert.doesNotMatch(webActions, /flex: 0 0 auto !important/);
assert.doesNotMatch(webActions, /width: max-content !important/);
assert.doesNotMatch(webActions, /MutationObserver/);
assert.doesNotMatch(webActions, /grid-template-columns: repeat\(auto-fit/);

assert.match(actionLayout, /background: transparent !important/);
assert.match(actionLayout, /border: 0 !important/);
assert.match(actionLayout, /padding: 0 !important/);
assert.match(actionLayout, /@media \(min-width: 701px\)/);
assert.match(actionLayout, /flex-basis: 0 !important/);
assert.doesNotMatch(actionLayout, /MutationObserver|IntersectionObserver|addEventListener\(["']scroll/);

// installed-mosaic.js still provides the legacy seven-track base. The later,
// intentional mobile-action-strip-six.js override owns the current six-action
// installed-app layout and hides the retired like control.
assert.match(installedMosaic, /grid-template-columns: repeat\(7, minmax\(0, 1fr\)\) !important/);
assert.match(installedMosaic, /data-community-comments/);
assert.match(installedMosaic, /data-community-like/);
assert.match(mobileSix, /grid-template-columns: repeat\(6, minmax\(0, 1fr\)\) !important/);
assert.match(mobileSix, /data-community-like/);
assert.match(mobileSix, /display: none !important/);

assert.match(shareQrCss, /header-search-toggle\[data-header-search-toggle\][\s\S]*width:100%!important/);
assert.match(shareQrCss, /data-installed-real-mosaic="true"[\s\S]*share-qr-button\[data-share-qr-open\][\s\S]*width:100%!important/);
assert.match(shareQrCss, /share-qr-button\[data-share-qr-open\][\s\S]*min-width:0!important/);
assert.match(shareQrCss, /share-qr-button\[data-share-qr-open\][\s\S]*justify-self:stretch!important/);

// Content modules have one runtime owner: app.js. pwa.js remains shell/UI only.
assert.match(app, /community-source\.js\?v=20260818-feedback3/);
assert.match(app, /participation-footer\.js\?v=20260819-feedback7/);
assert.doesNotMatch(pwa, /["']\.\/community-source\.js/);
assert.doesNotMatch(pwa, /["']\.\/participation-footer\.js/);
assert.match(pwa, /remove-like\.js\?v=20260819-remove3/);
assert.match(pwa, /installed-mosaic\.js\?v=20260818-f12-dual4/);
assert.match(pwa, /mobile-action-strip-six\.js\?v=20260819-actions7/);
assert.match(pwa, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(pwa, /action-strip-layout\.js\?v=20260818-fill1/);
// The service worker still caches the app-owned modules; caching is not runtime ownership.
assert.match(worker, /community-source\.js\?v=20260818-feedback3/);
assert.match(worker, /participation-footer\.js/);
assert.match(worker, /installed-mosaic\.js\?v=20260818-f12-dual4/);
assert.match(worker, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(worker, /action-strip-layout\.js\?v=20260818-fill1/);
assert.match(worker, /pwa\.js\?v=20260818-feedback6/);
const releaseMatch = release.match(/const RELEASE = (\d+);/);
assert.ok(releaseMatch, "release-version.js must expose a numeric RELEASE");
assert.ok(Number(releaseMatch[1]) >= 162, "PWA release must include single-owner feedback runtime");

console.log("Community feedback UI contract: single-owner content modules + current six-action installed strip");