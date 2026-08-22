import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { normalizePublicEventTitle } from "../public-title-normalizer.mjs";
import { canonicalVenueKey, normalizeVenueAliases, preferredVenueLabel } from "../venue-identity.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const read = (relative) => fs.readFileSync(path.join(app, relative), "utf8");

const valpoEvent = {
  location: { venue: "Teatro Mauri SCD", city: "Valparaíso" },
  primary_category: { id: "musica", label: "Música" },
};
const workshopEvent = {
  location: { venue: "Centro Cultural", city: "Viña del Mar" },
  primary_category: { id: "cursos-talleres", label: "Cursos y talleres" },
};
const gijonEvent = {
  location: { venue: "Museo Nicanor Piñole", city: "Gijón" },
  primary_category: { id: "exposiciones", label: "Exposiciones" },
};

assert.equal(normalizePublicEventTitle("QUILAPAYUN EN TEATRO MAURI SCD VALPARAÍSO", valpoEvent), "Quilapayun");
assert.equal(normalizePublicEventTitle("CICLO TALLER EL ARTE ES NATURAL", workshopEvent), "El arte es natural");
assert.equal(normalizePublicEventTitle("ALEJANDRO SIRIO. LA CALIGRAFÍA DEL DIBUJO", gijonEvent), "Alejandro Sirio. La caligrafía del dibujo");
assert.equal(normalizePublicEventTitle("INUNDAREMOS EN VALPARAÍSO - GIRA TANQUEMANTE", valpoEvent), "Inundaremos — Gira Tanquemante");
assert.equal(normalizePublicEventTitle("Juegos en Patota: DETECTIVES DEL ARTE.", gijonEvent), "Juegos en Patota: Detectives del arte");

const riojaMuseum = { location: { venue: "Museo Palacio Rioja", city: "Viña del Mar" } };
const riojaShort = { location: { venue: "Palacio Rioja", city: "Viña del Mar" } };
const riojaGarden = { location: { venue: "Jardines Palacio Rioja", city: "Viña del Mar" } };
const riojaRoom = { location: { venue: "Palacio Rioja, Sala Aldo Francia", city: "Viña del Mar" } };
assert.equal(canonicalVenueKey(riojaMuseum), canonicalVenueKey(riojaShort));
assert.notEqual(canonicalVenueKey(riojaMuseum), canonicalVenueKey(riojaGarden));
assert.equal(canonicalVenueKey(riojaMuseum), canonicalVenueKey(riojaRoom));
assert.equal(preferredVenueLabel(["Palacio Rioja", "Museo Palacio Rioja"]), "Museo Palacio Rioja");
const normalizedRioja = normalizeVenueAliases([riojaShort, riojaMuseum]);
assert.equal(normalizedRioja[0].location.venue, "Museo Palacio Rioja");
assert.equal(normalizedRioja[1].location.venue, "Museo Palacio Rioja");

const appJs = read("app.js");
const appCore = read("app-core.js");
const pipeline = read("data-pipeline.js");
const grouping = read("exhibition-groups.js");
const groupingCore = read("exhibition-group-core.mjs");
const cityAdapter = read("city-presentation-adapter.mjs");
const titleBootstrap = read("title-normalizer-bootstrap.js");
const cardExperience = read("card-experience.js");
const presentationGuard = read("public-presentation-guard.js");
const runtimeState = read("agenda-runtime-state.mjs");
const supplementBridge = read("supplemental-events-fetch.js");
const programPolicy = read("program-visibility-policy.js");
const filterSafety = read("combined-filters-safety.js");
const compactCss = read("exhibition-compact.css");
const exhibitionHours = read("exhibition-hours.js");
const scheduleDisplay = read("schedule-display.js");
const venueHours = read("venue-hours.mjs");
const generatedManifest = read("service-worker-assets.generated.js");

assert.match(appJs, /await coreReady;/);
assert.match(appJs, /exhibition-groups\.js/);
assert.doesNotMatch(appJs, /multievent-layout-fix\.js/);
assert.doesNotMatch(appJs, /exhibition-venue-grouping\.js|exhibition-gallery\.js|exhibition-compact-loader\.js|exhibition-compact\.js/);
assert.match(appCore, /function buildDatedItems\(/);
assert.match(appCore, /function createExhibitionGroupCard\(/);
assert.match(appCore, /card\.dataset\.eventGroup/);
assert.match(grouping, /getAgendaRuntimeSnapshot/);
assert.match(grouping, /function enhanceCoreGroups\(/);
assert.match(grouping, /groupStandaloneExhibitions/);
assert.match(grouping, /function reconcileCommonMembership\(/);
assert.doesNotMatch(grouping, /const\s+EXHIBITION_GROUP_MIN\s*=|function\s+clusterVenueExhibitions/);
assert.match(grouping, /unifiedExhibitionGroup/);
assert.match(grouping, /exhibition-venue-card/);
assert.match(grouping, /grouped-exhibition-item/);
assert.doesNotMatch(grouping, /\bfetch\s*\(/);
assert.match(groupingCore, /export const EXHIBITION_GROUP_MIN = 2/);
assert.match(groupingCore, /clusterSimultaneousExhibitions/);
assert.match(groupingCore, /exhibitionGroupingVenueKey/);
assert.match(cityAdapter, /eventForCityPresentation/);
assert.match(cityAdapter, /venueHoursForCity/);

for (const retired of [
  "exhibition-venue-grouping.js",
  "exhibition-gallery.js",
  "exhibition-compact-loader.js",
  "exhibition-compact.js",
  "multievent-layout-fix.js",
]) {
  assert.equal(fs.existsSync(path.join(app, retired)), false, `${retired} must stay retired`);
  assert.doesNotMatch(generatedManifest, new RegExp(retired.replaceAll(".", "\\.")));
}

assert.match(filterSafety, /requestCanonicalFilterPass/);
assert.match(filterSafety, /data-smart-search/);
assert.doesNotMatch(filterSafety, /static-exhibition-sentinels/);
assert.doesNotMatch(filterSafety, /\.hidden\s*=/);

assert.match(compactCss, /--agenda-group-row-min-height:\s*96px/);
assert.match(compactCss, /--agenda-group-list-max-height:\s*306px/);
assert.match(compactCss, /nth-child\(4\)/);
assert.match(compactCss, /overflow-wrap:\s*anywhere/);
assert.doesNotMatch(exhibitionHours, /style\.textContent|createElement\(["']style["']\)/);
assert.doesNotMatch(exhibitionHours, /venueHoursForDate|Horario del recinto:|\.textContent\s*=/);
assert.match(scheduleDisplay, /venueHoursForDate/);
assert.match(scheduleDisplay, /nextVenueOpeningForDate/);
assert.match(scheduleDisplay, /Horario del recinto:/);
assert.doesNotMatch(scheduleDisplay, /venueRecordForEvent|venueRecordForName/);
assert.match(venueHours, /venueRecordForEvent/);
assert.match(venueHours, /export function venueHoursForDate/);

assert.match(pipeline, /normalizeAgendaTitles/);
assert.match(pipeline, /normalizeAgendaCategories/);
assert.match(pipeline, /normalizeSessionOccurrences/);
assert.match(pipeline, /applyProgramVisibilityPolicy/);
assert.match(pipeline, /publishAgendaRuntimeSnapshot/);
assert.doesNotMatch(appJs, /^import "\.\/(?:title-normalizer-bootstrap|category-normalizer|supplemental-events-fetch|program-visibility-policy)\.js/m);
assert.doesNotMatch(titleBootstrap, /MutationObserver|IntersectionObserver/);
assert.doesNotMatch(titleBootstrap, /(?:window|globalThis|target)\.fetch\s*=/);

assert.match(runtimeState, /getAgendaRuntimeSnapshot/);
assert.match(cardExperience, /getAgendaRuntimeSnapshot/);
assert.doesNotMatch(cardExperience, /\bfetch\s*\(/);
assert.doesNotMatch(cardExperience, /new MutationObserver\s*\(/);
assert.match(presentationGuard, /getAgendaRuntimeSnapshot/);
assert.doesNotMatch(presentationGuard, /new MutationObserver\s*\(/);
assert.doesNotMatch(appJs, /card-title-consistency\.js/);

assert.match(pipeline, /city\?\.supplemental_dataset/);
assert.match(pipeline, /mergeSupplementalPayload\(base, supplementalResult\.payload\)/);
assert.match(supplementBridge, /export function mergeEvents/);
assert.match(supplementBridge, /export function mergeSupplementalPayload/);
assert.doesNotMatch(supplementBridge, /(?:window|globalThis|target)\.fetch\s*=/);
assert.doesNotMatch(programPolicy, /new MutationObserver\(/);
assert.doesNotMatch(programPolicy, /(?:window|globalThis|target)\.fetch\s*=/);
assert.match(programPolicy, /export function renderProgramReferences/);

console.log("Shared grouping policy + normalized runtime + shared presentation layout contract: OK");
