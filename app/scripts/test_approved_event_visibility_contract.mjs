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
assert.ok([...exhibitionVenueCounts.values()].some((count) => count >= 2), "Gijón must retain at least one multi-exhibition venue");

const appJs = read("app.js");
const bootstrap = read("combined-filters-bootstrap.js");
const integrity = read("approved-event-integrity.js");
const serviceWorker = read("service-worker.js");
const index = read("index.html");
const combined = read("combined-filters.js");

// Base rendering must never be gated behind a top-level await chain: a secondary
// presentation/filter failure must not prevent the public agenda from loading.
assert.match(appJs, /^import "\.\/category-normalizer\.js/m);
assert.match(appJs, /^import "\.\/app-core\.js/m);
assert.doesNotMatch(appJs, /__vivamosAppBaseReady|await\s+baseReady|const\s+baseReady/);
assert.match(bootstrap, /import "\.\/category-normalizer\.js/);
assert.match(bootstrap, /const filtersReady = import\("\.\/combined-filters\.js/);
assert.match(bootstrap, /\.then\(\(\) => import\("\.\/approved-event-integrity\.js/);
assert.doesNotMatch(bootstrap, /waitForBaseApp|await\s+waitForBaseApp/);
assert.match(index, /src="\.\/combined-filters-bootstrap\.js"/);
assert.doesNotMatch(index, /src="\.\/combined-filters\.js"/);

assert.match(combined, /forceBaseAppFilters\(\)/);
assert.match(combined, /data-section-filter="todos"/);
assert.match(integrity, /approvedIds/);
assert.match(integrity, /representations\(\)/);
assert.match(integrity, /data-event-group/);
assert.match(integrity, /missing approved event representations/);
assert.match(integrity, /approved events hidden without active filters/);
assert.match(integrity, /forceCompleteBaseRender/);
assert.match(integrity, /reapplyModernFilters/);
assert.match(serviceWorker, /"\.\/combined-filters-bootstrap\.js"/);
assert.match(serviceWorker, /"\.\/approved-event-integrity\.js"/);

console.log(`Approved event visibility contract: OK (${valpoIds.size} Valparaíso/Viña + ${gijonIds.size} Gijón approved events; non-blocking startup)`);
