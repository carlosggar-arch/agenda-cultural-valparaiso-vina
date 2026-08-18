import assert from "node:assert/strict";
import fs from "node:fs";

const js = fs.readFileSync(new URL("../app/community-source.js", import.meta.url), "utf8");
const participation = fs.readFileSync(new URL("../app/participation-footer.js", import.meta.url), "utf8");
const webActions = fs.readFileSync(new URL("../app/web-actions-below-mosaic.js", import.meta.url), "utf8");
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
assert.match(participation, /width: max-content !important/);
assert.match(participation, /min-height: 36px !important/);
assert.match(participation, /overflow-x: auto !important/);
assert.match(participation, /restoreFooterContact/);
assert.doesNotMatch(participation, /MutationObserver|IntersectionObserver|addEventListener\(["']scroll/);

assert.match(webActions, /display: flex !important/);
assert.match(webActions, /flex: 0 0 auto !important/);
assert.match(webActions, /width: max-content !important/);
assert.match(webActions, /min-height: 36px !important/);
assert.match(webActions, /overflow-x: auto !important/);
assert.doesNotMatch(webActions, /MutationObserver/);
assert.doesNotMatch(webActions, /grid-template-columns: repeat\(auto-fit/);

assert.match(app, /community-source\.js\?v=20260818-feedback3/);
assert.match(app, /participation-footer\.js\?v=20260818-feedback6/);
assert.match(pwa, /community-source\.js\?v=20260818-feedback3/);
assert.match(pwa, /participation-footer\.js\?v=20260818-feedback6/);
assert.match(pwa, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(worker, /community-source\.js\?v=20260818-feedback3/);
assert.match(worker, /participation-footer\.js\?v=20260818-feedback6/);
assert.match(worker, /web-actions-below-mosaic\.js\?v=20260818-web2/);
assert.match(worker, /pwa\.js\?v=20260818-feedback6/);
assert.match(release, /const RELEASE = 103/);

console.log("Community feedback UI contract: compact comments + like beside Aportar fuente in WEB + PWA");
