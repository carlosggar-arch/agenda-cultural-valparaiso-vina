import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { eventForCityPresentation } from "./city-presentation-adapter.mjs";
import { enrichCitySourceEvidence } from "./city-source-evidence-adapter.mjs";
import { normalizeAgendaSourceEvidence } from "./source-evidence-normalizer.mjs";

function read(relative) {
  return readFileSync(new URL(relative, import.meta.url), "utf8");
}

function prepareGijonPresentation(event) {
  const enriched = enrichCitySourceEvidence(event, "gijon");
  const canonical = normalizeAgendaSourceEvidence({ events: [enriched] }).events[0];
  return eventForCityPresentation(canonical, "gijon");
}

const app = read("./app.js");
const runtime = read("./agenda-runtime-state.mjs");
const firstRun = read("./city-first-run.js");
const temporalCleanup = read("./temporal-priority.js");
const visibilityOwnerCore = read("./visibility-owner-core.mjs");
const combinedFilters = read("./combined-filters.js");
const exhibitionGroups = read("./exhibition-groups.js");
const exhibitionCore = read("./exhibition-group-core.mjs");
const dataQuality = read("./event-card-data-quality.mjs");
const scheduleDisplay = read("./schedule-display.js");
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
const snapshotConsumers = sharedPresentationModules.filter((modulePath) => modulePath !== "./temporal-priority.js");

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
for (const modulePath of snapshotConsumers) {
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

assert.match(temporalCleanup, /removeLegacyTemporalUi/, "temporal cleanup must retain removal of retired temporal UI");
assert.doesNotMatch(temporalCleanup, /getAgendaRuntimeSnapshot|loadAgendaDataset|loadCityRegistry|\.hidden\s*=|temporalSuppressed/, "cleanup-only temporal module must not own data or visibility");
assert.doesNotMatch(temporalCleanup, explicitCityConstant, "temporal cleanup must remain city-agnostic");
assert.match(visibilityOwnerCore, /shouldSuppressForTemporalFilter/, "visibility core must retain temporal-confidence semantics");
assert.match(combinedFilters, /visibility-owner-core\.mjs/, "combined filters must consume the canonical visibility core");

assert.match(
  scheduleDisplay,
  /Horario de hoy:/,
  "exhibition cards must label a date-specific visit status instead of appending an ambiguous bare value",
);
assert.doesNotMatch(
  scheduleDisplay,
  /return daily\.label;/,
  "a closed venue must never be rendered as an unexplained bare ‘Cerrado’ beside the exhibition dates",
);
assert.match(
  scheduleDisplay,
  /nextDailyExhibitionOpening/,
  "closed exhibitions must resolve the next valid venue opening through the shared date-aware hours module",
);
assert.match(
  scheduleDisplay,
  /Próxima apertura:/,
  "closed exhibition cards must expose the next actionable visiting interval when one exists",
);

const nuncaEsTarde = prepareGijonPresentation({
  id: "agenda_gijon_a3925dadc26ffa27",
  source_id: "gijon_opendata_events",
  source_name: "Open Data Ayuntamiento de Gijón/Xixón — Agenda de Eventos",
  source_url: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
  links: {
    official: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
    source: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
    municipal_page: "https://www.gijon.es/nunca-es-tarde-para-pintar",
  },
  public_status: { external_link_quality: "opendata_fallback" },
  schedule: {
    mode: "multi_day",
    start: "2026-08-04",
    end: "2026-08-28",
    display_text: "2026-08-04 · 00:00",
    occurrences: [],
    opening_hours: { display_text: "De lunes a viernes: de 08:00 a 21:30 horas." },
  },
  location: {
    venue_id: "157",
    venue: "Centro Municipal Integrado El Coto",
    city: "Gijón",
  },
});
assert.equal(nuncaEsTarde.links.presentation_source, "https://www.gijon.es/nunca-es-tarde-para-pintar");
assert.equal(nuncaEsTarde.links.official, "https://www.gijon.es/nunca-es-tarde-para-pintar");
assert.equal(nuncaEsTarde.source_url, "https://www.gijon.es/nunca-es-tarde-para-pintar");
assert.equal(nuncaEsTarde.source_name, "Ayuntamiento de Gijón/Xixón");

const mientrasDormias = prepareGijonPresentation({
  id: "agenda_gijon_b034ca0ffc281bb1",
  source_id: "gijon_opendata_events",
  source_name: "Open Data Ayuntamiento de Gijón/Xixón — Agenda de Eventos",
  source_url: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
  links: {
    official: "https://drupal.gijon.es/es/exposicion-mientras-tu-dormias",
    source: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
    municipal_page: "https://www.gijon.es/exposicion-mientras-tu-dormias",
  },
  public_status: { external_link_quality: "direct_official" },
  schedule: {
    mode: "multi_day",
    start: "2026-07-30T09:00:00+02:00",
    end: "2026-08-27",
    display_text: "2026-07-30 · 09:00",
    occurrences: [],
    opening_hours: { display_text: "De lunes a sábado de 08:00 a 21:30 horas." },
  },
  location: {
    venue_id: "156",
    venue: "Centro Municipal Integrado Ateneo de La Calzada",
    city: "Gijón",
  },
});
assert.equal(mientrasDormias.links.presentation_source, "https://www.gijon.es/exposicion-mientras-tu-dormias");
assert.equal(mientrasDormias.source_name, "Ayuntamiento de Gijón/Xixón");
assert.equal(mientrasDormias.schedule.opening_time, "09:00");
assert.equal(mientrasDormias.schedule.closing_time, "21:00");
assert.equal(mientrasDormias.schedule.hours_confidence, "official_event_page");

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
