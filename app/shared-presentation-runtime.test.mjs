import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

function read(relative) {
  return readFileSync(new URL(relative, import.meta.url), "utf8");
}

const app = read("./app.js");
const runtime = read("./agenda-runtime-state.mjs");
const firstRun = read("./city-first-run.js");
const exhibitionGroups = read("./exhibition-groups.js");
const exhibitionCore = read("./exhibition-group-core.mjs");
const dataQuality = read("./event-card-data-quality.mjs");
const commonBlock = app.match(/const OPTIONAL_MODULES = \[([\s\S]*?)\];/)?.[1] || "";
const sharedPresentationModules = [
  "./temporal-priority.js",
  "./exhibition-groups.js",
  "./exhibition-hours.js",
  "./schedule-display.js",
  "./event-card-data-quality.mjs",
  "./card-experience.js",
  "./public-presentation-guard.js",
  "./image-quality-guard.js",
];

for (const modulePath of sharedPresentationModules) {
  const moduleName = modulePath.replace("./", "");
  assert.match(
    commonBlock,
    new RegExp(moduleName.replaceAll(".", "\\.")),
    `${moduleName} must be loaded by the common presentation runtime`,
  );
}

assert.doesNotMatch(
  app,
  /GIJON_DEFERRED_MODULES|IS_GIJON|gijon-card-images|card-image-fallback/,
  "app.js must not select a renderer or image layer by city",
);

assert.match(
  runtime,
  /eventForCityPresentation\(event, cityId\)/,
  "city-specific presentation differences must enter through the runtime adapter boundary",
);
assert.match(
  runtime,
  /presentationEvents/,
  "the shared runtime must publish adapted presentation events",
);

const explicitCityConstant = /["'](?:gijon|valparaiso|America\/Santiago|Europe\/Madrid|es-CL|es-ES)["']/i;
for (const modulePath of sharedPresentationModules) {
  const source = read(modulePath);
  assert.match(
    source,
    /getAgendaRuntimeSnapshot/,
    `${modulePath} must consume the shared runtime snapshot`,
  );
  assert.doesNotMatch(
    source,
    /fetch\([^\n]*\.dataset|loadCityRegistry\(\)[\s\S]*?fetch\(/,
    `${modulePath} must not maintain a parallel city dataset runtime`,
  );
  assert.doesNotMatch(
    source,
    explicitCityConstant,
    `${modulePath} must not hardcode concrete cities, city timezones or city locales`,
  );
}

assert.match(
  exhibitionGroups,
  /groupStandaloneExhibitions/,
  "the final exhibition membership pass must consume the shared grouping policy",
);
assert.match(
  exhibitionGroups,
  /exhibition-group-core\.mjs/,
  "exhibition membership rules must live in the common grouping module",
);
assert.doesNotMatch(
  exhibitionGroups,
  /const\s+EXHIBITION_GROUP_MIN\s*=|function\s+clusterVenueExhibitions/,
  "the renderer must not redeclare the grouping threshold or clustering algorithm",
);
assert.match(
  exhibitionCore,
  /export const EXHIBITION_GROUP_MIN = 2/,
  "the common grouping core owns the minimum cardinality",
);
assert.match(
  dataQuality,
  /schedule_contract_version/,
  "legacy card quality logic must defer to the canonical Point 8 schedule contract",
);
assert.doesNotMatch(
  dataQuality,
  /schedule\.textContent\s*=\s*`\$\{schedule\.textContent\.trim\(\)\}/,
  "venue hours must never be concatenated back into the event-time line",
);

assert.doesNotMatch(
  firstRun,
  /window\.location\.(?:assign|replace)|location\.reload/,
  "switching city must not require a document reload",
);
assert.match(firstRun, /loadCityRegistry/, "first-run city choices must come from the canonical registry");
assert.match(firstRun, /SUPPORTED_CITIES/, "first-run validation must be registry-driven");
assert.match(firstRun, /releaseRequiredSelection/, "first-run may release the chooser lock after a valid selection");
assert.doesNotMatch(firstRun, /loadAgendaDataset|setAgendaCity/, "first-run must not own dataset reload or dynamic city switching");

assert.equal(
  existsSync(new URL("./gijon-card-images.js", import.meta.url)),
  false,
  "the Gijon-specific card renderer must stay retired",
);
assert.equal(
  existsSync(new URL("./card-image-fallback.js", import.meta.url)),
  false,
  "the duplicate card fallback renderer must stay retired",
);

console.log("SHARED_PRESENTATION_RUNTIME_CONTRACT_OK");
