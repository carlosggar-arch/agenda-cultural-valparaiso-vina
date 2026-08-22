import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const core = readFileSync(new URL("./app-core.js", import.meta.url), "utf8");
const presentation = readFileSync(new URL("./exhibition-groups.js", import.meta.url), "utf8");
const grouping = readFileSync(new URL("./exhibition-group-core.mjs", import.meta.url), "utf8");
const venueIdentity = readFileSync(new URL("./venue-identity.mjs", import.meta.url), "utf8");

assert.match(
  core,
  /from "\.\/exhibition-group-core\.mjs/,
  "core rendering must consume the shared exhibition grouping module",
);
assert.match(
  core,
  /groupStandaloneExhibitions\(events, \{ timezone:/,
  "core initial grouping must use the shared membership policy",
);
assert.match(
  core,
  /compareAgendaOrder/,
  "top-level exhibition cards must use the canonical agenda ordering authority",
);
assert.doesNotMatch(
  core,
  /isLongExhibitionDuration/,
  "core must not maintain a parallel long-exhibition ordering rule after C1",
);
assert.doesNotMatch(
  core,
  /const\s+EXHIBITION_GROUP_MIN\s*=|const\s+LONG_EXHIBITION_DAYS\s*=|function\s+clusterVenueExhibitions|function\s+exhibitionRange|function\s+exhibitionVenueKey/,
  "core must not maintain a second grouping threshold, duration threshold, clustering algorithm or venue identity",
);
assert.match(
  presentation,
  /groupStandaloneExhibitions/,
  "presentation reconciliation must consume the same shared grouping policy",
);
assert.match(
  presentation,
  /function reconcileCommonMembership\(\)/,
  "the renderer must reconcile initial cards through common membership",
);
assert.match(
  grouping,
  /export const EXHIBITION_GROUP_MIN = 2/,
  "the common grouping core owns group cardinality",
);
assert.match(
  grouping,
  /export const LONG_EXHIBITION_DAYS = 7/,
  "the common grouping core owns the reusable long-exhibition duration threshold",
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
  "reconciliation must never split grouped cards or lose unrelated exhibitions",
);

console.log("EXHIBITION_GROUP_SINGLE_POLICY_OK");
