import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function read(path) {
  return readFileSync(new URL(path, import.meta.url), "utf8");
}

const app = read("./app.js");
const core = read("./app-core.js");
const pipeline = read("./data-pipeline.js");
const startup = read("./startup-stability.js");
const pwa = read("./pwa.js");
const programPolicy = read("./program-visibility-policy.js");
const worker = read("./service-worker.js");
const release = read("./release-version.js");

assert.match(app, /^import "\.\/startup-stability\.js/m, "startup watchdog must be the only eager startup dependency");
assert.match(app, /await import\("\.\/app-core\.js/, "core must be a dynamic import so the watchdog can run first");
assert.match(app, /const \{ coreReady \} = await import/, "app.js must wait for the core-ready contract");
assert.match(app, /await coreReady;/, "optional enhancements must wait until core startup completes");
assert.match(app, /Promise\.allSettled\(OPTIONAL_MODULES\.map\(\(module\) => import\(module\)\)\)/, "optional app modules must fail independently");
for (const critical of [
  "supplemental-events-fetch.js",
  "event-data-corrections.js",
  "category-normalizer.js",
  "title-normalizer-bootstrap.js",
  "session-occurrence-normalizer.js",
  "program-visibility-policy.js",
]) {
  assert.doesNotMatch(app, new RegExp(`^import\\s+["']\\./${critical.replaceAll(".", "\\.")}`, "m"), `${critical} must not be an eager app.js side-effect import`);
}

assert.match(app, /const GIJON_DEFERRED_MODULES = new Set/, "Gijon must have an explicit stable-core enhancement boundary");
for (const deferred of ["temporal-priority.js", "static-exhibition-groups.js", "multievent-layout-fix.js", "schedule-display.js"]) {
  assert.match(app, new RegExp(`GIJON_DEFERRED_MODULES[\\s\\S]*${deferred.replaceAll(".", "\\.")}`), `${deferred} must stay deferred on Gijon startup`);
}

assert.match(core, /import \{ loadAgendaDataset \} from "\.\/data-pipeline\.js/, "app-core must own the data pipeline");
assert.match(core, /export const coreReady = new Promise/, "app-core must expose startup readiness");
assert.match(core, /function markCoreReady\(/, "app-core must explicitly settle startup");
assert.match(core, /dataset\.vivamosReady = "true"/, "app-core must mark the DOM ready itself");
assert.match(core, /renderProgramReferences\(/, "program references must be rendered explicitly from core");

const stageOrder = [
  "applyEventDataCorrections",
  "normalizeAgendaCategories",
  "normalizeAgendaTitles",
  "normalizeSessionOccurrences",
  "applyProgramVisibilityPolicy",
].map((name) => pipeline.indexOf(name));
assert.equal(stageOrder.every((index) => index >= 0), true, "all data-pipeline stages must be present");
assert.deepEqual([...stageOrder].sort((a, b) => a - b), stageOrder, "data-pipeline stage order must remain deterministic");
assert.match(pipeline, /function applyStage\(/, "pipeline stages must be isolated behind a failure boundary");
assert.match(pipeline, /status: "skipped"/, "pipeline must continue when an optional transform fails");

for (const file of [
  "./supplemental-events-fetch.js",
  "./event-data-corrections.js",
  "./category-normalizer.js",
  "./title-normalizer-bootstrap.js",
  "./session-occurrence-normalizer.js",
  "./program-visibility-policy.js",
]) {
  const source = read(file);
  assert.doesNotMatch(
    source,
    /(?:window|globalThis|target)\.fetch\s*=/,
    `${file} must never monkey-patch the global fetch function`,
  );
}

assert.doesNotMatch(programPolicy, /new MutationObserver\(/, "program visibility must not depend on DOM observation");
assert.match(programPolicy, /export function renderProgramReferences\(/, "program visibility must expose an explicit renderer");

assert.doesNotMatch(startup, /new MutationObserver\(/, "startup watchdog must not depend on a MutationObserver");
assert.match(startup, /SAFE_MODE_DELAY_MS\s*=\s*5000/, "startup watchdog must activate safe mode promptly");
assert.match(startup, /import\("\.\/app-safe-mode\.js/, "watchdog must have an independent safe-mode entry point");
assert.match(startup, /vivamos:core-ready/, "watchdog must stop when core is ready");

assert.match(pwa, /const OPTIONAL_UI_MODULES = \[/, "PWA enhancements must be declared optional");
assert.match(pwa, /vivamos:core-ready/, "PWA enhancements must wait for core readiness");
assert.match(pwa, /Promise\.allSettled\(OPTIONAL_UI_MODULES\.map\(\(module\) => import\(module\)\)\)/, "PWA optional modules must fail independently");
assert.doesNotMatch(pwa, /^import\s+["']\.\/(?:card-experience|public-presentation-guard|schedule-display|header-redesign|favorites)\.js/m, "PWA presentation modules must not be eager imports");
assert.match(pwa, /const GIJON_DEFERRED_UI_MODULES = new Set/, "Gijon must explicitly defer observer-heavy PWA presentation layers");
for (const deferred of ["card-experience.js", "public-presentation-guard.js", "schedule-display.js", "exhibition-hours.js", "card-image-fallback.js"]) {
  assert.match(pwa, new RegExp(`GIJON_DEFERRED_UI_MODULES[\\s\\S]*${deferred.replaceAll(".", "\\.")}`), `${deferred} must stay out of the Gijon stable UI path`);
}

assert.match(worker, /"\.\/data-pipeline\.js"/, "service worker must cache the resilient data pipeline");
assert.match(worker, /"\.\/app-safe-mode\.js"/, "service worker must cache safe mode");
assert.match(worker, /"\.\/startup-stability\.js"/, "service worker must cache the startup watchdog");
assert.match(release, /const RELEASE = 133;/, "Gijon date-filter visibility fix must force a fresh service-worker cache generation");

console.log("STARTUP_ARCHITECTURE_OK");
