import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const core = readFileSync(new URL("./app-core.js", import.meta.url), "utf8");
const presentation = readFileSync(new URL("./exhibition-groups.js", import.meta.url), "utf8");
const grouping = readFileSync(new URL("./exhibition-group-core.mjs", import.meta.url), "utf8");
const venueIdentity = readFileSync(new URL("./venue-identity.mjs", import.meta.url), "utf8");

assert.match(
  core,
  /function buildDatedItems\(events\)/,
  "app-core may keep emitting initial groups during the migration",
);
assert.match(
  presentation,
  /groupStandaloneExhibitions/,
  "the final runtime membership pass must consume the shared grouping policy",
);
assert.match(
  presentation,
  /function reconcileCommonMembership\(\)/,
  "the renderer must reconcile legacy initial groups against common membership",
);
assert.match(
  grouping,
  /export const EXHIBITION_GROUP_MIN = 2/,
  "the common grouping core owns group cardinality",
);
assert.match(
  grouping,
  /exhibitionGroupingVenueKey/,
  "the common grouping core must use shared exhibition venue identity",
);
assert.match(
  venueIdentity,
  /parentComplexLabel/,
  "subspace-to-complex identity must be structural and shared",
);
assert.doesNotMatch(
  presentation,
  /const\s+EXHIBITION_GROUP_MIN\s*=|function\s+clusterVenueExhibitions/,
  "the presentation layer must not maintain a second threshold or clustering algorithm",
);
assert.match(
  presentation,
  /safeMerge/,
  "legacy cards must never be split or lose unrelated exhibitions during reconciliation",
);

console.log("EXHIBITION_GROUP_SHARED_AUTHORITY_OK");
