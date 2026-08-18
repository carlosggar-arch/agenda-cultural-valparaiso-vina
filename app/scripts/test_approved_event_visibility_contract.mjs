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
const bootstrap = read("combined-filters-bootstrap.js");
const release = read("release-version.js");
const index = read("index.html");
const combined = read("combined-filters.js");
const grouping = read("static-exhibition-groups.js");
const titleBootstrap = read("title-normalizer-bootstrap.js");

assert.match(appJs, /^import "\.\/category-normalizer\.js/m);
assert.match(appJs, /^import "\.\/title-normalizer-bootstrap\.js/m);
assert.match(appJs, /^import "\.\/app-core\.js/m);
assert.match(appJs, /^import "\.\/static-exhibition-groups\.js/m);
assert.match(appJs, /^import "\.\/footer-credit\.js/m);
assert.doesNotMatch(appJs, /exhibition-venue-grouping|exhibition-gallery\.js|exhibition-compact-loader|presentation-normalizer\.js/);

// Permanent runtime rule: grouping is allowed only as an observer-free, bounded
// transformation. Approved events remain addressable through filter sentinels.
assert.match(grouping, /MIN_GROUP_SIZE = 2/);
assert.match(grouping, /staticExhibitionSentinels/);
assert.doesNotMatch(grouping, /MutationObserver|IntersectionObserver|getBoundingClientRect|offsetHeight|addEventListener\(["']scroll/);
assert.doesNotMatch(titleBootstrap, /MutationObserver|IntersectionObserver/);

assert.match(bootstrap, /^import "\.\/category-normalizer\.js/m);
assert.match(bootstrap, /await import\("\.\/combined-filters\.js\?v=20260818-public-taxonomy1"\)/);
assert.doesNotMatch(bootstrap, /approved-event-integrity|MutationObserver|repair\(/);
assert.match(index, /src="\.\/combined-filters-bootstrap\.js"/);
assert.doesNotMatch(index, /src="\.\/combined-filters\.js"/);

assert.match(combined, /forceBaseAppFilters\(\)/);
assert.match(combined, /data-section-filter="todos"/);
assert.match(release, /const RELEASE = 92/);
assert.doesNotMatch(release, /serviceWorker|window\.stop|caches\.delete|pwa_recovered/);

console.log(`Approved event visibility contract: OK (${valpoIds.size} Valparaíso/Viña + ${gijonIds.size} Gijón approved events; static observer-free grouping)`);
