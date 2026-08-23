import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const read = (relative) => fs.readFileSync(path.join(app, relative), "utf8");

const structuralContracts = [
  "shared-presentation-runtime.test.mjs",
  "startup-architecture.test.mjs",
  "exhibition-group-architecture.test.mjs",
  "scripts/test_third_city_architecture.py",
  "scripts/test_multi_city_ui.py",
  "scripts/test_static_grouping_title_contract.mjs",
  "scripts/test_approved_event_visibility_contract.mjs",
  "scripts/test_structural_hardening.py",
  "scripts/test_pre_release.py",
];

const forbiddenCouplings = [
  {
    pattern: /\bRELEASE\b[^\n]*>=\s*\d+|releaseNumber[^\n]*>=\s*\d+|int\([^\n]*release[^\n]*\)\s*>=\s*\d+/i,
    reason: "architecture contracts must not depend on a numeric release milestone",
  },
  {
    pattern: /app-core\.js owns city changes|sole authority|single owner/i,
    reason: "architecture contracts must validate interfaces and behavior, not explanatory ownership prose",
  },
  {
    pattern: /historical CI|compatibility tombstone|after the v\d+ recovery/i,
    reason: "historical recovery/tombstone wording must not become a permanent architecture requirement",
  },
  {
    pattern: /static-exhibition-groups\.js/i,
    reason: "retired compatibility modules must not remain part of structural contracts",
  },
  {
    pattern: /data\/valparaiso\/supplemental-events\.json/i,
    reason: "optional supplemental data is a registry capability, not a city-specific architecture invariant",
  },
];

for (const relative of structuralContracts) {
  const source = read(relative);
  for (const { pattern, reason } of forbiddenCouplings) {
    assert.doesNotMatch(source, pattern, `${relative}: ${reason}`);
  }
}

assert.equal(
  fs.existsSync(path.join(app, "static-exhibition-groups.js")),
  false,
  "the historical static exhibition compatibility marker must stay removed",
);

const appCore = read("app-core.js");
const agendaOrder = read("agenda-order-core.mjs");
const exhibitionGroupCore = read("exhibition-group-core.mjs");
assert.match(appCore, /from "\.\/exhibition-group-core\.mjs/, "app-core must consume the canonical exhibition grouping module");
assert.match(appCore, /groupStandaloneExhibitions\(/, "app-core initial grouping must use the canonical membership policy");
assert.match(appCore, /compareAgendaOrder\(/, "app-core top-level ordering must use the canonical agenda order");
assert.doesNotMatch(appCore, /isLongExhibitionDuration\(/, "app-core must not reintroduce a parallel long-exhibition ordering rule");
assert.match(agendaOrder, /from "\.\/temporal-priority-core\.mjs/, "agenda order must consume the shared temporal core");
assert.match(agendaOrder, /TEMPORAL_BUCKETS/, "agenda order must use the shared temporal bucket hierarchy");
assert.match(agendaOrder, /classifyTemporalEvent\(/, "agenda order must use the shared temporal classifier");
assert.match(agendaOrder, /eventDateRanges\(/, "agenda order must reuse canonical temporal date ranges");
assert.doesNotMatch(
  agendaOrder,
  /(?:const|let|var)\s+(?:TEMPORAL_BUCKETS|CONTENT_KINDS)\s*=/,
  "agenda order must not redeclare canonical temporal vocabularies",
);
assert.match(exhibitionGroupCore, /export const LONG_EXHIBITION_DAYS = 7/, "grouping core must retain its reusable long-exhibition threshold");
assert.doesNotMatch(
  appCore,
  /const\s+EXHIBITION_GROUP_MIN\s*=|const\s+LONG_EXHIBITION_DAYS\s*=|function\s+clusterVenueExhibitions|function\s+exhibitionRange|function\s+exhibitionVenueKey/,
  "app-core must not reintroduce a second exhibition policy",
);

console.log("ARCHITECTURE_CONTRACT_HYGIENE_OK");
