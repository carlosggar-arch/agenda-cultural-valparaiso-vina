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
const visibilityOwnerCore = read("./visibility-owner-core.mjs");
const exhibitionGroups = read("./exhibition-groups.js");
const exhibitionGroupCore = read("./exhibition-group-core.mjs");
const exhibitionPresentationGuard = read("./exhibition-presentation-guard.js");
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
assert.match(app, /new MutationObserver\(scheduleTemporalOrder\)/, "shared temporal ordering may use bounded direct-grid observers");
assert.doesNotMatch(app, /observe\(datedGrid, \{[^}]*subtree:\s*true/, "shared ordering must never observe descendant churn");
assert.match(app, /compareAgendaOrder/, "post-render ordering must use the canonical agenda-order authority");
assert.doesNotMatch(app, /compareTemporalPriority/, "app.js must not bypass agenda-order-core");

assert.match(core, /import \{ loadAgendaDataset \} from "\.\/data-pipeline\.js/, "core startup must consume the canonical data pipeline");
assert.match(core, /export const coreReady = new Promise/, "core startup must expose readiness");
assert.match(core, /function markCoreReady\(/, "core startup must explicitly settle readiness");
assert.match(core, /dataset\.vivamosReady = "true"/, "core startup must mark the DOM ready");
assert.match(core, /renderProgramReferences\(/, "program references must be rendered explicitly");
assert.match(core, /function buildDatedItems\(events, now = new Date\(\)\)/, "core may emit canonically ordered initial grouped cards before common reconciliation");
assert.match(core, /from "\.\/exhibition-group-core\.mjs/, "core grouping must consume the canonical exhibition policy");
assert.match(core, /groupStandaloneExhibitions\(events, \{ timezone:/, "core initial grouping must use canonical membership");
assert.match(core, /compareAgendaOrder/, "core top-level ordering must use the canonical agenda-order authority");
assert.doesNotMatch(core, /isLongExhibitionDuration/, "core must not maintain a parallel long-exhibition ordering rule");
assert.doesNotMatch(core, /const\s+EXHIBITION_GROUP_MIN\s*=|const\s+LONG_EXHIBITION_DAYS\s*=|function\s+clusterVenueExhibitions|function\s+exhibitionRange|function\s+exhibitionVenueKey/, "core must not duplicate exhibition policy");

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

assert.doesNotMatch(temporalPriority, /\bfetch\s*\(|loadCityRegistry|getAgendaRuntimeSnapshot|\.hidden\s*=|temporalSuppressed/, "temporal presentation must not own event visibility or data loading");
assert.match(temporalPriority, /removeLegacyTemporalUi/, "temporal module must retain bounded legacy UI cleanup");
assert.match(visibilityOwnerCore, /shouldSuppressForTemporalFilter/, "visibility core must preserve temporal confidence semantics");
assert.match(combined, /visibility-owner-core\.mjs/, "combined filters must consume canonical visibility decisions");
assert.match(combined, /card\.hidden\s*=/, "combined filters must own top-level card hidden state");
assert.match(combined, /rows\[index\]\.hidden\s*=/, "combined filters must own grouped-row hidden state");
assert.match(combined, /dataset\.temporalSuppressed/, "combined filters must own temporal visual suppression");
assert.doesNotMatch(exhibitionPresentationGuard, /\.hidden\s*=/, "exhibition presentation guard must not write visibility");
assert.match(exhibitionPresentationGuard, /vivamos:visibility-reconcile-requested/, "exhibition consolidation must delegate visibility reconciliation");

assert.match(exhibitionGroups, /getAgendaRuntimeSnapshot/, "shared exhibition renderer must consume normalized runtime state");
assert.match(exhibitionGroups, /function enhanceCoreGroups\(\)/, "shared exhibition renderer must enhance existing grouped cards");
assert.match(exhibitionGroups, /groupStandaloneExhibitions/, "shared exhibition renderer must consume the canonical grouping policy");
assert.match(exhibitionGroups, /function reconcileCommonMembership\(\)/, "shared exhibition renderer must reconcile initial groups against common membership");
assert.doesNotMatch(exhibitionGroups, /const\s+EXHIBITION_GROUP_MIN\s*=|function\s+clusterVenueExhibitions/, "renderer must not duplicate the common threshold or clustering algorithm");
assert.doesNotMatch(exhibitionGroups, /\bfetch\s*\(/, "shared exhibition renderer must never re-fetch datasets");
assert.match(exhibitionGroups, /new MutationObserver/, "shared exhibition renderer may react to direct grid/city transitions");
assert.doesNotMatch(exhibitionGroups, /subtree:\s*true|characterData:\s*true/, "shared exhibition renderer must not watch descendant churn");
assert.match(exhibitionGroupCore, /export const EXHIBITION_GROUP_MIN = 2/, "common grouping core owns exhibition group cardinality");
assert.match(exhibitionGroupCore, /export const LONG_EXHIBITION_DAYS = 7/, "common grouping core owns long-exhibition duration");
assert.match(exhibitionGroupCore, /exhibitionGroupingVenueKey/, "common grouping core owns canonical exhibition venue identity");
assert.match(cityPresentationAdapter, /export function eventForCityPresentation/, "city-specific event adaptation must enter through the public adapter boundary");
assert.match(cityPresentationAdapter, /export function venueHoursForCity/, "city-specific venue hours must enter through the public adapter boundary");

assert.doesNotMatch(cityFirstRun, /window\.location\.(?:assign|replace)|location\.reload/, "city switching must not reload the document");
assert.match(cityFirstRun, /loadCityRegistry/, "first-run city choices must come from the canonical registry");
assert.match(cityFirstRun, /SUPPORTED_CITIES/, "first-run validation must be registry-driven");
assert.match(cityFirstRun, /releaseRequiredSelection/, "first-run may release the chooser lock after a valid selection");
assert.doesNotMatch(cityFirstRun, /loadAgendaDataset|setAgendaCity/, "first-run must not own dataset loading or dynamic city switching");

assert.match(combined, /loadAgendaDataset/, "combined filters must use the same normalized pipeline as the renderer");
assert.match(combined, /canonicalPublicCategory/, "combined filters must delegate category aliases to the shared taxonomy");
assert.match(core, /canonicalPublicCategory/, "core presentation must delegate category aliases to the shared taxonomy");
assert.doesNotMatch(combined, /MUSEUM_CATEGORY_ID|id\s*===\s*["']museos["']|id\s*=\s*["']exposiciones["']/, "combined filters must not maintain category aliases locally");
assert.doesNotMatch(core, /MUSEUM_CATEGORY_ID|id\s*===\s*["']museos["']|id\s*=\s*["']exposiciones["']/, "core presentation must not maintain category aliases locally");
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
  "./agenda-order-core.mjs",
  "./visibility-owner-core.mjs",
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

console.log("STARTUP_ARCHITECTURE_SHARED_PRESENTATION_OK");
