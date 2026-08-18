import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolvePublicCategory } from "../public-category-rules.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const dataset = JSON.parse(fs.readFileSync(path.join(app, "data/gijon/agenda_web.json"), "utf8"));
const exposures = dataset.events.filter((event) => resolvePublicCategory(event).id === "exposiciones");
assert.ok(exposures.length > 5, `Gijón public Exposiciones unexpectedly collapsed to ${exposures.length}`);

const byVenue = new Map();
for (const event of exposures) {
  const venue = String(event?.location?.venue || "").trim();
  if (!venue) continue;
  byVenue.set(venue, (byVenue.get(venue) || 0) + 1);
}
assert.ok([...byVenue.values()].some((count) => count >= 2), "Gijón must retain multi-exhibition venues");

const index = fs.readFileSync(path.join(app, "index.html"), "utf8");
const bootstrap = fs.readFileSync(path.join(app, "combined-filters-bootstrap.js"), "utf8");
assert.match(index, /src="\.\/combined-filters-bootstrap\.js"/);
assert.doesNotMatch(index, /src="\.\/combined-filters\.js"/);
const normalizerPos = bootstrap.indexOf("category-normalizer.js");
const filtersPos = bootstrap.indexOf("combined-filters.js");
assert.ok(normalizerPos >= 0 && filtersPos > normalizerPos, "taxonomy normalizer must load before combined filters");

console.log(`Gijón exhibition filter contract: OK (${exposures.length} public exhibitions; ${[...byVenue.values()].filter((count) => count >= 2).length} multi-exhibition venues)`);
