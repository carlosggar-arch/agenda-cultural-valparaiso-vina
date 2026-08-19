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
assert.notEqual(canonicalVenueKey(riojaMuseum), canonicalVenueKey(riojaRoom));
assert.equal(preferredVenueLabel(["Palacio Rioja", "Museo Palacio Rioja"]), "Museo Palacio Rioja");
const normalizedRioja = normalizeVenueAliases([riojaShort, riojaMuseum]);
assert.equal(normalizedRioja[0].location.venue, "Museo Palacio Rioja");
assert.equal(normalizedRioja[1].location.venue, "Museo Palacio Rioja");

const appJs = read("app.js");
const grouping = read("static-exhibition-groups.js");
const titleBootstrap = read("title-normalizer-bootstrap.js");
const compactCss = read("exhibition-compact.css");
const multieventFix = read("multievent-layout-fix.js");
const supplementBridge = read("supplemental-events-fetch.js");
const release = read("release-version.js");

assert.match(appJs, /title-normalizer-bootstrap\.js/);
assert.match(appJs, /static-exhibition-groups\.js/);
assert.match(appJs, /multievent-layout-fix\.js/);
assert.doesNotMatch(appJs, /exhibition-venue-grouping|exhibition-gallery\.js|exhibition-compact-loader|presentation-normalizer\.js/);
assert.doesNotMatch(grouping, /MutationObserver|IntersectionObserver|getBoundingClientRect|offsetHeight|addEventListener\(["']scroll/);
assert.doesNotMatch(titleBootstrap, /MutationObserver|IntersectionObserver/);
assert.match(grouping, /MIN_GROUP_SIZE = 2/);
assert.match(grouping, /staticExhibitionSentinels/);
assert.match(compactCss, /\.event-grid\s*\{[^}]*align-items:\s*stretch\s*!important/s);
assert.match(compactCss, /\.event-grid\s*>\s*\.event-card\s*\{[^}]*align-self:\s*stretch\s*!important/s);
assert.doesNotMatch(compactCss, /align-items:\s*start\s*!important/);
assert.doesNotMatch(compactCss, /align-self:\s*start\s*!important/);
assert.match(multieventFix, /\.grouped-exhibition-item[\s\S]*height:\s*auto\s*!important/);
assert.match(multieventFix, /\.grouped-exhibition-item[\s\S]*max-height:\s*none\s*!important/);
assert.match(multieventFix, /\.grouped-exhibition-copy strong[\s\S]*-webkit-line-clamp:\s*unset\s*!important/);
assert.match(multieventFix, /\.grouped-exhibition-copy small[\s\S]*white-space:\s*normal\s*!important/);
assert.doesNotMatch(multieventFix, /Palacio Rioja/);

const cities = JSON.parse(read("cities.json"));
const valparaiso = cities.cities.find((city) => city.id === "valparaiso");
assert.equal(valparaiso?.supplemental_dataset, "./data/valparaiso/supplemental-events.json");
const supplemental = JSON.parse(read("data/valparaiso/supplemental-events.json"));
assert.equal(supplemental.events?.length, 1);
const decadencia = supplemental.events[0];
assert.equal(decadencia.title, "Presentación libro // “Decadencia”");
assert.equal(decadencia.primary_category?.id, "otros");
assert.equal(decadencia.primary_category?.label, "Otros panoramas");
assert.equal(decadencia.schedule?.start, "2026-08-27T18:00:00-04:00");
assert.equal(decadencia.schedule?.end, "2026-08-27T20:00:00-04:00");
assert.equal(decadencia.location?.venue, "Palacio Rioja");
assert.equal(decadencia.public_status?.source_official, true);
assert.doesNotMatch(appJs, /supplemental-events-fetch\.js/, "supplemental fetch interception must stay out of the critical startup path while the production freeze is investigated");
assert.doesNotMatch(appJs, /program-visibility-policy\.js/, "program DOM/fetch interception must stay out of the critical startup path while the production freeze is investigated");
assert.match(supplementBridge, /supplemental_dataset/);
assert.match(supplementBridge, /mergeEvents/);
assert.doesNotMatch(supplementBridge, /Decadencia|Palacio Rioja/);

const releaseMatch = release.match(/const RELEASE = (\d+);/);
assert.ok(releaseMatch, "release-version.js must expose a numeric RELEASE");
assert.ok(Number(releaseMatch[1]) >= 126, "PWA release must include the emergency startup unfreeze");

const gijon = JSON.parse(fs.readFileSync(path.join(app, "data/gijon/agenda_web.json"), "utf8"));
const venues = new Map();
for (const event of gijon.events || []) {
  const id = String(event?.primary_category?.id || event?.categories?.[0]?.id || "");
  if (!["exposiciones", "museos"].includes(id)) continue;
  const venue = String(event?.location?.venue || "").trim();
  if (venue) venues.set(venue, (venues.get(venue) || 0) + 1);
}
assert.ok([...venues.values()].some((count) => count >= 2), "Gijón must retain venues with multiple exhibitions");

console.log("Static grouping + venue identity + unclipped multievent layout + startup fail-open contract: OK");
