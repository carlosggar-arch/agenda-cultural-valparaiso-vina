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
const exhibitionGroups = read("./exhibition-groups.js");
const exhibitionGroupCore = read("./exhibition-group-core.mjs");
const cityPresentationAdapter = read("./city-presentation-adapter.mjs");
const cityFirstRun = read("./city-first-run.js");
const cardExperience = read("./card-experience.js");
const imageQualityGuard = read("./image-quality-guard.js");
const presentationGuard = read("./public-presentation-guard.js");
const scheduleDisplay = read("./schedule-display.js");
const exhibitionHours = read("./exhibition-hours.js");
const temporalPriority = read("./temporal-priority.js");
const programPolicy = read("./program-visibility-policy.js");
const worker = read("./service-worker.js");
const shellManifest = read("./service-worker-assets.generated.js");
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

// Every city uses the same presentation runtime. Differences belong to data,
// configuration or the city presentation adapter, not to renderer selection.
for (const shared of [
  "temporal-priority.js",
  "exhibition-groups.js",
  "schedule-display.js",
  "exhibition-hours.js",
  "card-experience.js",
  "public-presentation-guard.js",
  "image-quality-guard.js",
]) {
  assert.match(app, new RegExp(shared.replaceAll(".", "\\.")), `${shared} must be present in the common runtime`);
}
assert.doesNotMatch(app, /GIJON_DEFERRED_MODULES|IS_GIJON|gijon-card-images\.js|card-image-fallback\.js/, "app.js must not select presentation modules by city");
assert.doesNotMatch(app, /static-exhibition-groups\.js/, "legacy Valpo-only exhibition renderer must not be loaded");
assert.match(app, /new MutationObserver\(scheduleTemporalOrder\)/, "shared temporal ordering may use bounded direct-grid observers");
assert.doesNotMatch(app, /observe\(datedGrid, \{[^}]*subtree:\s*true/, "shared ordering must never observe descendant churn");

assert.match(core, /import \{ loadAgendaDataset \} from "\.\/data-pipeline\.js/, "app-core must own the data pipeline");
assert.match(core, /export const coreReady = new Promise/, "app-core must expose startup readiness");
assert.match(core, /function markCoreReady\(/, "app-core must explicitly settle startup");
assert.match(core, /dataset\.vivamosReady = "true"/, "app-core must mark the DOM ready itself");
assert.match(core, /renderProgramReferences\(/, "program references must be rendered explicitly from core");
assert.match(core, /function buildDatedItems\(events\)/, "app-core must remain the sole runtime grouping authority");

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
assert.match(runtimeState, /eventForCityPresentation\(event, cityId\)/, "runtime state must apply city differences at the adapter boundary");

assert.match(lifecycle, /new MutationObserver/, "render lifecycle may own one bounded observer");
assert.match(lifecycle, /observe\(root, \{ childList: true \}\)/, "render lifecycle must watch only direct grid membership");
assert.doesNotMatch(lifecycle, /subtree:\s*true/, "render lifecycle must not observe descendant churn");
assert.doesNotMatch(lifecycle, /characterData:\s*true/, "render lifecycle must not observe text churn");
assert.match(lifecycle, /vivamos:agenda-rendered/, "render lifecycle must publish explicit render completion events");

for (const [name, source] of [
  ["card-experience", cardExperience],
  ["image-quality-guard", imageQualityGuard],
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
assert.doesNotMatch(temporalPriority, /\bfetch\s*\(|loadCityRegistry/, "temporal presentation must consume the shared runtime rather than loading a city dataset");
assert.match(temporalPriority, /getAgendaRuntimeSnapshot/, "temporal presentation must consume the shared runtime snapshot");

// Canonical exhibition membership is decided by app-core. The shared exhibition
// module only enriches that group into the rich visual presentation.
assert.match(exhibitionGroups, /getAgendaRuntimeSnapshot/, "shared exhibition renderer must consume normalized runtime state");
assert.match(exhibitionGroups, /function enhanceCoreGroups\(\)/, "shared exhibition renderer must enhance existing core groups");
assert.doesNotMatch(exhibitionGroups, /groupStandaloneExhibitions|groupStandaloneCards|EXHIBITION_GROUP_MIN/, "shared exhibition renderer must not run a second grouping algorithm");
assert.doesNotMatch(exhibitionGroups, /\bfetch\s*\(/, "shared exhibition renderer must never re-fetch datasets");
assert.match(exhibitionGroups, /new MutationObserver/, "shared exhibition renderer may react to direct grid/city transitions");
assert.doesNotMatch(exhibitionGroups, /subtree:\s*true|characterData:\s*true/, "shared exhibition renderer must not watch descendant churn");
assert.match(exhibitionGroupCore, /EXHIBITION_GROUP_MIN = 2/, "the pure grouping model remains available for deterministic tests and future core extraction");
assert.match(cityPresentationAdapter, /scheduleForGijonEvent/, "Gijon schedule differences must stay in the city adapter");
assert.match(cityPresentationAdapter, /gijonLocationForEvent/, "Gijon location differences must stay in the city adapter");

assert.doesNotMatch(cityFirstRun, /window\.location\.(?:assign|replace)|location\.reload/, "city switching must not reload the document");
assert.match(cityFirstRun, /app-core\.js owns city changes/, "first-run logic must leave dynamic city switching to app-core");

assert.match(combined, /loadAgendaDataset/, "combined filters must use the same normalized pipeline as the renderer");
assert.match(combined, /id === "museos"[\s\S]*id = "exposiciones"/, "Museos must collapse into Exposiciones in filter semantics");
assert.match(combined, /\.event-card\[data-event-group\]/, "grouped exhibitions must participate in filtering");
assert.match(combined, /rows\[index\]\.hidden/, "grouped exhibition children must respect active filters");

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
  '"./gijon-card-images.js"',
]) {
  assert.equal(pwa.includes(marker), false, `pwa.js must not instantiate content presentation module ${marker}`);
}

for (const asset of [
  "./data-pipeline.js",
  "./agenda-runtime-state.mjs",
  "./render-lifecycle.js",
  "./exhibition-groups.js",
  "./exhibition-group-core.mjs",
  "./city-presentation-adapter.mjs",
  "./app-safe-mode.js",
  "./startup-stability.js",
]) {
  assert.match(shellManifest, new RegExp(`"${asset.replaceAll(".", "\\.")}"`), `generated shell must cache ${asset}`);
}
assert.doesNotMatch(shellManifest, /card-image-fallback\.js|gijon-card-images\.js/, "generated shell must not cache retired renderers");
assert.match(worker, /service-worker-assets\.generated\.js/, "service worker must load the generated shell manifest");
assert.doesNotMatch(worker, /const SHELL_ASSETS = \[/, "service worker must not restore a manual shell asset list");
const releaseNumber = Number(release.match(/const RELEASE = (\d+);/)?.[1]);
assert.ok(Number.isInteger(releaseNumber) && releaseNumber >= 182, "shared presentation runtime requires a fresh service-worker cache generation");

console.log("STARTUP_ARCHITECTURE_SHARED_PRESENTATION_OK");
