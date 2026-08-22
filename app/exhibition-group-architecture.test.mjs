import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const core = readFileSync(new URL("./app-core.js", import.meta.url), "utf8");
const presentation = readFileSync(new URL("./exhibition-groups.js", import.meta.url), "utf8");

assert.match(
  core,
  /function buildDatedItems\(events\)/,
  "app-core must remain the single runtime owner of exhibition group membership",
);
assert.match(
  core,
  /createExhibitionGroupCard\(/,
  "app-core must emit the canonical data-event-group cards",
);
assert.match(
  presentation,
  /function enhanceCoreGroups\(\)/,
  "exhibition-groups must only enrich groups emitted by app-core",
);
assert.match(
  presentation,
  /app-core\.js is the sole authority for exhibition membership/,
  "the ownership boundary must be explicit in the presentation layer",
);
assert.doesNotMatch(
  presentation,
  /groupStandaloneExhibitions|groupStandaloneCards|clusterVenueExhibitions|EXHIBITION_GROUP_MIN/,
  "the presentation layer must not run a second grouping algorithm",
);
assert.doesNotMatch(
  presentation,
  /dataset\.eventId[\s\S]*?insertBefore|nodeById[\s\S]*?\.remove\(\)/,
  "standalone cards must never be regrouped by the presentation layer",
);

console.log("EXHIBITION_GROUP_SINGLE_AUTHORITY_OK");
