import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function read(path) {
  return readFileSync(new URL(path, import.meta.url), "utf8");
}

const app = read("./app.js");
const core = read("./app-core.js");
const pipeline = read("./data-pipeline.js");
const runtimeState = read("./agenda-runtime-state.mjs");
const lifecycle = read("./render-lifecycle.js");
const startup = read("./startup-stability.js");
const pwa = read("./pwa.js");
const combined = read("./combined-filters.js");
const gijonImages = read("./gijon-card-images.js");
const cardExperience = read("./card-experience.js");
const imageFallback = read("./card-image-fallback.js");
const presentationGuard = read("./public-presentation-guard.js");
const scheduleDisplay = read("./schedule-display.js");
const exhibitionHours = read("./exhibition-hours.js");
const programPolicy = read("./program-visibility-policy.js");
const worker = read("./service-worker.js");
const release = read("./release-version.js");

assert.match(app, /^import "\.\/startup-stability\.js/m, "startup watchdog must remain eager before core");
assert.match(app, /^import "\.\/render-lifecycle\.js/m, "bounded render lifecycle must start before deferred enhancers");
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
assert.match(app, /gijon-card-images\.js/, "Gijon must restore images through a lightweight stable-core enhancer");
assert.match(app, /if \(!IS_GIJON\)[\s\S]*new MutationObserver\(scheduleExhibitionOrder\)/, "Gijon must stay out of the grid-order observer path");
for (const module of ["card-experience.js", "card-image-fallback.js", "public-presentation-guard.js", "exhibition-hours.js"]) {
  assert.match(app, new RegExp(module.replaceAll(".", "\\.")), `${module} must be owned by app.js on the rich runtime`);
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
assert.match(pipeline, /publishAgendaRuntimeSnapshot/, "pipeline must publish the final normalized result for runtime consumers");
assert.match(runtimeState, /vivamos:agenda-data-ready/, "runtime state must announce normalized data readiness");
assert.match(runtimeState, /getAgendaRuntimeSnapshot/, "runtime state must expose the current normalized snapshot");

assert.match(lifecycle, /new MutationObserver/, "render lifecycle may own one bounded observer");
assert.match(lifecycle, /observe\(root, \{ childList: true \}\)/, "render lifecycle must watch only direct grid membership");
assert.doesNotMatch(lifecycle, /subtree:\s*true/, "render lifecycle must not observe descendant churn");
assert.doesNotMatch(lifecycle, /characterData:\s*true/, "render lifecycle must not observe text churn");
assert.match(lifecycle, /vivamos:agenda-rendered/, "render lifecycle must publish explicit render completion events");

for (const [name, source] of [
  ["card-experience", cardExperience],
  ["card-image-fallback", imageFallback],
  ["public-presentation-guard", presentationGuard],
  ["schedule-display", scheduleDisplay],
  ["exhibition-hours", exhibitionHours],
]) {
  assert.match(source, /getAgendaRuntimeSnapshot/, `${name} must consume the shared normalized runtime state`);
  assert.match(source, /vivamos:agenda-rendered/, `${name} must react to explicit render lifecycle events`);
  assert.doesNotMatch(source, /new MutationObserver\s*\(/, `${name} must not install its own DOM observer`);
  assert.doesNotMatch(source, /loadAgendaDataset/, `${name} must not rerun the data pipeline`);
}
assert.doesNotMatch(cardExperience, /\bfetch\s*\(/, "rich card rendering must never re-fetch raw data");
assert.doesNotMatch(presentationGuard, /\bfetch\s*\(/, "presentation guard must never re-fetch raw data");
assert.doesNotMatch(exhibitionHours, /\bfetch\s*\(/, "exhibition hours must never re-fetch raw data");

assert.match(combined, /loadAgendaDataset/, "combined filters must use the same normalized pipeline as the renderer");
assert.match(combined, /id === "museos"[\s\S]*id = "exposiciones"/, "Museos must collapse into Exposiciones in filter semantics");
assert.match(combined, /\.event-card\[data-event-group\]/, "grouped exhibitions must participate in filtering");
assert.match(combined, /rows\[index\]\.hidden/, "grouped exhibition children must respect active filters");
assert.match(gijonImages, /loadAgendaDataset\(city\)/, "Gijon images must use the normalized agenda pipeline");
assert.match(gijonImages, /\.event-card\[data-event-id\]/, "Gijon image enrichment must target stable core cards directly");
assert.doesNotMatch(gijonImages, /childList\s*:\s*true/, "Gijon image enrichment must not observe the event grid");

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
for (const marker of [
  '"./card-experience.js"',
  '"./public-presentation-guard.js"',
  '"./schedule-display.js',
  '"./exhibition-hours.js',
  '"./card-image-fallback.js"',
]) {
  assert.equal(pwa.includes(marker), false, `pwa.js must not instantiate content presentation module ${marker}`);
}

assert.match(worker, /"\.\/data-pipeline\.js"/, "service worker must cache the resilient data pipeline");
assert.match(worker, /agenda-runtime-state\.mjs/, "service worker must cache shared normalized runtime state");
assert.match(worker, /render-lifecycle\.js/, "service worker must cache the bounded render lifecycle");
assert.match(worker, /"\.\/app-safe-mode\.js"/, "service worker must cache safe mode");
assert.match(worker, /"\.\/startup-stability\.js"/, "service worker must cache the startup watchdog");
const releaseNumber = Number(release.match(/const RELEASE = (\d+);/)?.[1]);
assert.ok(Number.isInteger(releaseNumber) && releaseNumber >= 144, "render lifecycle hardening requires a fresh service-worker cache generation");

console.log("STARTUP_ARCHITECTURE_OK");
