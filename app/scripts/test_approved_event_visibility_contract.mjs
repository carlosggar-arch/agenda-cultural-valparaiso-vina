import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolvePublicCategory } from "../public-category-rules.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const root = path.resolve(app, "..");

function read(relative) {
  return fs.readFileSync(path.join(app, relative), "utf8");
}

function loadJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function validateDataset(name, dataset) {
  assert.ok(Array.isArray(dataset.events), `${name}: events must be an array`);
  const ids = dataset.events.map((event) => String(event?.id || "").trim());
  assert.ok(ids.every(Boolean), `${name}: every approved event must have an id`);
  assert.equal(new Set(ids).size, ids.length, `${name}: approved event ids must be unique`);
  assert.equal(dataset.counts?.total, dataset.events.length, `${name}: counts.total must equal approved events length`);
  return new Set(ids);
}

const valpo = loadJson(path.join(root, "agenda_web.json"));
const gijon = loadJson(path.join(app, "data/gijon/agenda_web.json"));
const valpoIds = validateDataset("Valparaíso/Viña", valpo);
const gijonIds = validateDataset("Gijón", gijon);
assert.ok(valpoIds.size > 0 && gijonIds.size > 0, "both cities must retain approved events");

const gijonExhibitions = gijon.events.filter((event) => resolvePublicCategory(event).id === "exposiciones");
assert.ok(gijonExhibitions.length > 5, `Gijón Exposiciones unexpectedly collapsed to ${gijonExhibitions.length}`);
const exhibitionVenueCounts = new Map();
for (const event of gijonExhibitions) {
  const venue = String(event?.location?.venue || "").trim();
  if (venue) exhibitionVenueCounts.set(venue, (exhibitionVenueCounts.get(venue) || 0) + 1);
}
assert.ok([...exhibitionVenueCounts.values()].some((count) => count >= 2), "Gijón must retain multi-exhibition venue data");

const appJs = read("app.js");
const appCore = read("app-core.js");
const pipeline = read("data-pipeline.js");
const bootstrap = read("combined-filters-bootstrap.js");
const index = read("index.html");
const combined = read("combined-filters.js");
const grouping = read("exhibition-groups.js");
const groupingCore = read("exhibition-group-core.mjs");
const titleBootstrap = read("title-normalizer-bootstrap.js");
const categoryNormalizer = read("category-normalizer.js");

// The startup entry point stays thin and one shared renderer owns grouped
// exhibition presentation for every city after coreReady.
assert.match(appJs, /^import "\.\/startup-stability\.js/m);
assert.match(appJs, /await import\("\.\/app-core\.js/);
assert.match(appJs, /await coreReady;/);
assert.match(appJs, /exhibition-groups\.js/);
assert.match(appJs, /footer-credit\.js/);
assert.doesNotMatch(appJs, /^import "\.\/(?:category-normalizer|title-normalizer-bootstrap|session-occurrence-normalizer|program-visibility-policy)\.js/m);
assert.doesNotMatch(appJs, /exhibition-venue-grouping|exhibition-gallery\.js|exhibition-compact-loader|presentation-normalizer\.js/);

// Approved-event normalization is deterministic and uses the same canonical
// data pipeline as the combined filters.
assert.match(appCore, /loadAgendaDataset/);
assert.match(pipeline, /applyEventDataCorrections/);
assert.match(pipeline, /normalizeAgendaCategories/);
assert.match(pipeline, /normalizeAgendaTitles/);
assert.match(pipeline, /normalizeSessionOccurrences/);
assert.match(pipeline, /applyProgramVisibilityPolicy/);
assert.doesNotMatch(categoryNormalizer, /(?:window|globalThis|target)\.fetch\s*=/);
assert.doesNotMatch(titleBootstrap, /(?:window|globalThis|target)\.fetch\s*=/);
assert.doesNotMatch(titleBootstrap, /MutationObserver|IntersectionObserver/);

// Initial and presentation grouping share one pure policy. Neither consumer may
// redeclare cardinality, duration, venue identity or clustering.
assert.match(appCore, /from "\.\/exhibition-group-core\.mjs/);
assert.match(appCore, /groupStandaloneExhibitions\(events, \{ timezone:/);
assert.match(appCore, /isLongExhibitionDuration/);
assert.doesNotMatch(appCore, /const\s+EXHIBITION_GROUP_MIN\s*=|const\s+LONG_EXHIBITION_DAYS\s*=|function\s+clusterVenueExhibitions|function\s+exhibitionRange|function\s+exhibitionVenueKey/);
assert.match(grouping, /getAgendaRuntimeSnapshot/);
assert.match(grouping, /function enhanceCoreGroups\(/);
assert.match(grouping, /groupStandaloneExhibitions/);
assert.match(grouping, /function reconcileCommonMembership\(/);
assert.match(grouping, /unifiedExhibitionGroup/);
assert.doesNotMatch(grouping, /const\s+EXHIBITION_GROUP_MIN\s*=|function\s+clusterVenueExhibitions/);
assert.doesNotMatch(grouping, /\bfetch\s*\(/);
assert.match(groupingCore, /export const EXHIBITION_GROUP_MIN = 2/);
assert.match(groupingCore, /export const LONG_EXHIBITION_DAYS = 7/);
assert.match(groupingCore, /clusterSimultaneousExhibitions/);
assert.match(groupingCore, /exhibitionGroupingVenueKey/);

// Combined filters can still import pure category helpers, but must load through
// a versioned module and use the normalized agenda pipeline.
assert.match(bootstrap, /^import "\.\/category-normalizer\.js/m);
assert.match(bootstrap, /await import\("\.\/combined-filters\.js\?v=[^"]+"\)/);
assert.doesNotMatch(bootstrap, /approved-event-integrity|MutationObserver|repair\(/);
assert.match(index, /src="\.\/combined-filters-bootstrap\.js"/);
assert.doesNotMatch(index, /src="\.\/combined-filters\.js"/);
assert.match(combined, /loadAgendaDataset/);
assert.doesNotMatch(combined, /fetch\(CITY_CONFIG\[cityId\]\.dataset/);
assert.match(combined, /forceBaseAppFilters\(\)/);
assert.match(combined, /data-section-filter="todos"/);

console.log(`Approved event visibility contract: OK (${valpoIds.size} Valparaíso/Viña + ${gijonIds.size} Gijón approved events; shared normalized pipeline + single exhibition policy)`);
