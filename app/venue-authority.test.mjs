import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  canonicalVenueKey,
  exhibitionGroupingVenueKey,
  normalizeVenueAliases,
} from "./venue-identity.mjs";
import { eventForCityPresentation } from "./city-presentation-adapter.mjs";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const categoryNormalizer = read("./category-normalizer.js");
const pipeline = read("./data-pipeline.js");
const runtime = read("./agenda-runtime-state.mjs");

const fixtures = [
  {
    id: "rioja-alias",
    title: "Exposición de prueba",
    location: { venue: "Palacio Rioja", city: "Viña del Mar" },
  },
  {
    id: "gijon-alias",
    title: "Actividad de prueba",
    location: { venue: "CMI L'Arena", city: "Gijón" },
  },
];

const normalized = normalizeVenueAliases(fixtures);
assert.equal(normalized[0].location.venue, "Museo Palacio Rioja");
assert.equal(normalized[1].location.venue, "Centro Municipal Integrado L'Arena");
assert.deepEqual(normalizeVenueAliases(normalized), normalized, "venue normalization must be idempotent");
assert.equal(canonicalVenueKey(fixtures[0]), canonicalVenueKey(normalized[0]), "canonical identity must survive alias normalization");
assert.equal(exhibitionGroupingVenueKey(fixtures[0]), exhibitionGroupingVenueKey(normalized[0]), "visual exhibition grouping must not change");

const gijonPlaceholder = {
  id: "gijon-placeholder",
  title: "Actividad sin recinto verificable",
  location: { venue: "Gijón/Xixón", city: "Gijón/Xixón" },
  links: {},
};
const adaptedPlaceholder = eventForCityPresentation(gijonPlaceholder, "gijon");
const finalizedPlaceholder = normalizeVenueAliases([adaptedPlaceholder])[0];
assert.equal(finalizedPlaceholder.location.venue, "", "intentional Gijón placeholder removal must remain intact");
assert.equal(finalizedPlaceholder.location.city, "", "placeholder city-as-venue cleanup must remain intact");

assert.doesNotMatch(categoryNormalizer, /venue-identity|normalizeVenueAliases|canonicalVenueKey/, "category normalization must not own venue identity");
assert.match(pipeline, /from "\.\/venue-identity\.mjs/, "pipeline must consume canonical venue identity directly");
assert.match(pipeline, /"venue-identity-normalizer"/, "pipeline must expose venue identity as an explicit semantic stage");
assert.ok(
  pipeline.indexOf('"venue-identity-normalizer"') < pipeline.indexOf('"cross-source-deduplication"'),
  "early venue canonicalization must stay before dedupe to preserve C5 behavior",
);
assert.match(runtime, /normalizeVenueAliases\(adaptedEvents\)/, "runtime boundary must finalize venue identity after city adapters");
assert.ok(
  runtime.indexOf("eventForCityPresentation") < runtime.lastIndexOf("normalizeVenueAliases(adaptedEvents)"),
  "city adapter corrections must enter venue identity before reaching presentation",
);
assert.ok(
  runtime.lastIndexOf("normalizeVenueAliases(adaptedEvents)") < runtime.indexOf("normalizeEventScheduleContract(event)"),
  "venue identity must be finalized before schedule presentation contracts",
);

console.log("SINGLE_VENUE_AUTHORITY_OK");
