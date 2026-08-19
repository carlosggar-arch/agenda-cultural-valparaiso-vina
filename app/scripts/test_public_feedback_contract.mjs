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
const mobileSix = read("mobile-action-strip-six.js");
const shareQrCss = read("share-qr.css");
const appJs = read("app.js");
const pwa = read("pwa.js");
const worker = read("service-worker.js");
const release = read("release-version.js");

// The feedback API and pending-like storage remain supported by the data layer,
// even though the retired like control is no longer shown in the public action strip.
for (const marker of ["Comentarios", "data-community-like", "FEEDBACK_API", "/likes", "/comments", "LIKE_PENDING_KEY", "syncPendingLike"]) {
  assert.match(community, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
}
assert.match(community, /data-like-count>0/);
assert.match(community, /storageSet\(LIKED_KEY, "1"\)/);

// Current public header: mount comments after Contribuir and remove any legacy
// like node. The installed mobile override owns a six-action, gapless strip.
assert.match(participation, /mountHeaderFeedback/);
assert.match(participation, /\.header-actions/);
assert.match(participation, /data-contribute-source/);
assert.match(participation, /insertAdjacentElement\("afterend", comments\)/);
assert.match(participation, /querySelectorAll\("\[data-community-like\], \.source-like-button"\)\.forEach\(\(node\) => node\.remove\(\)\)/);
assert.doesNotMatch(participation, /insertAdjacentElement\("afterend", like\)/);
assert.match(participation, /restoreFooterContact/);
assert.match(participation, /grid-template-columns: repeat\(6, minmax\(0, 1fr\)\) !important/);
assert.doesNotMatch(participation, /IntersectionObserver|addEventListener\(["']scroll/);

assert.match(webActions, /display: flex !important/);
assert.match(webActions, /overflow-x: auto !important/);
assert.doesNotMatch(webActions, /MutationObserver/);
assert.doesNotMatch(webActions, /grid-template-columns: repeat\(auto-fit/);

assert.match(actionLayout, /background: transparent !important/);
assert.match(actionLayout, /border: 0 !important/);
assert.match(actionLayout, /padding: 0 !important/);
assert.match(actionLayout, /flex-basis: 0 !important/);
assert.doesNotMatch(actionLayout, /MutationObserver|IntersectionObserver|addEventListener\(["']scroll/);

// installed-mosaic.js is the legacy seven-track base; the later mobile-six
// module is the intentional current override and hides the retired like action.
assert.match(installedMosaic, /grid-template-columns: repeat\(7, minmax\(0, 1fr\)\) !important/);
assert.match(installedMosaic, /data-community-comments/);
assert.match(installedMosaic, /data-community-like/);
assert.match(mobileSix, /grid-template-columns: repeat\(6, minmax\(0, 1fr\)\) !important/);
assert.match(mobileSix, /data-community-like/);
assert.match(mobileSix, /display: none !important/);

assert.match(shareQrCss, /header-search-toggle\[data-header-search-toggle\][\s\S]*width:100%!important/);
assert.match(shareQrCss, /data-installed-real-mosaic="true"[\s\S]*share-qr-button\[data-share-qr-open\][\s\S]*width:100%!important/);
assert.match(shareQrCss, /share-qr-button\[data-share-qr-open\][\s\S]*justify-self:stretch!important/);

assert.match(appJs, /community-source\.js\?v=20260818-feedback3/);
assert.match(appJs, /participation-footer\.js\?v=20260819-feedback7/);
assert.match(pwa, /community-source\.js\?v=20260818-feedback3/);
assert.match(pwa, /remove-like\.js\?v=20260819-remove3/);
assert.match(pwa, /participation-footer\.js\?v=20260819-feedback7/);
assert.match(pwa, /installed-mosaic\.js\?v=20260818-f12-dual4/);
assert.match(pwa, /mobile-action-strip-six\.js\?v=20260819-actions7/);
assert.match(pwa, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(pwa, /action-strip-layout\.js\?v=20260818-fill1/);
assert.match(worker, /community-source\.js\?v=20260818-feedback3/);
assert.match(worker, /participation-footer\.js/);
assert.match(worker, /installed-mosaic\.js\?v=20260818-f12-dual4/);
assert.match(worker, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(worker, /action-strip-layout\.js\?v=20260818-fill1/);
assert.match(worker, /pwa\.js\?v=20260818-feedback6/);
const releaseMatch = release.match(/const RELEASE = (\d+);/);
assert.ok(releaseMatch, "release-version.js must expose a numeric RELEASE");
assert.ok(Number(releaseMatch[1]) >= 114, "PWA release must not regress below v114");

console.log("Public feedback: current comments-only six-action installed strip contract: OK");
