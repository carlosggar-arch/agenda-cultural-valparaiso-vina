import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { normalizePublicEventTitle } from "../public-title-normalizer.mjs";
import { canonicalVenueKey, normalizeVenueAliases, preferredVenueLabel } from "../venue-identity.mjs";
import { venueHoursForEvents } from "../venue-hours.mjs";

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

const riojaHours = venueHoursForEvents([riojaMuseum], "valparaiso");
assert.equal(riojaHours?.display, "Mar–dom 10:00–17:30.");
const naturalHistoryHours = venueHoursForEvents([
  { location: { venue: "Museo de Historia Natural de Valparaíso", city: "Valparaíso" } },
], "valparaiso");
assert.match(naturalHistoryHours?.display || "", /Mar–vie 10:00–18:00/);
const gijonHours = venueHoursForEvents([gijonEvent], "gijon");
assert.match(gijonHours?.display || "", /09:30–14:00/);
const explicitHours = venueHoursForEvents([
  {
    location: { venue: "Museo Palacio Rioja", city: "Viña del Mar" },
    schedule: { opening_hours: { display_text: "Horario especial verificado" } },
  },
], "valparaiso");
assert.equal(explicitHours?.display, "Horario especial verificado");

const appJs = read("app.js");
const grouping = read("static-exhibition-groups.js");
const titleBootstrap = read("title-normalizer-bootstrap.js");
const compactCss = read("exhibition-compact.css");
const multieventFix = read("multievent-layout-fix.js");
const release = read("release-version.js");

assert.match(appJs, /title-normalizer-bootstrap\.js/);
assert.match(appJs, /static-exhibition-groups\.js/);
assert.match(appJs, /multievent-layout-fix\.js/);
assert.doesNotMatch(appJs, /exhibition-venue-grouping|exhibition-gallery\.js|exhibition-compact-loader|presentation-normalizer\.js/);
assert.doesNotMatch(grouping, /MutationObserver|IntersectionObserver|getBoundingClientRect|offsetHeight|addEventListener\(["']scroll/);
assert.doesNotMatch(titleBootstrap, /MutationObserver|IntersectionObserver/);
assert.match(grouping, /MIN_GROUP_SIZE = 2/);
assert.match(grouping, /staticExhibitionSentinels/);
assert.match(grouping, /venueHoursForEvents/);
assert.match(grouping, /Horario de visita:/);
assert.match(compactCss, /\.event-grid\s*\{[^}]*align-items:\s*stretch\s*!important/s);
assert.match(compactCss, /\.event-grid\s*>\s*\.event-card\s*\{[^}]*align-self:\s*stretch\s*!important/s);
assert.doesNotMatch(compactCss, /align-items:\s*start\s*!important/);
assert.doesNotMatch(compactCss, /align-self:\s*start\s*!important/);
assert.match(multieventFix, /\.grouped-exhibition-item[\s\S]*height:\s*auto\s*!important/);
assert.match(multieventFix, /\.grouped-exhibition-item[\s\S]*min-height:\s*92px\s*!important/);
assert.match(multieventFix, /\.grouped-exhibition-item[\s\S]*max-height:\s*none\s*!important/);
assert.match(multieventFix, /\.grouped-exhibition-copy > \*[\s\S]*white-space:\s*normal\s*!important/);
assert.match(multieventFix, /\.grouped-exhibition-price[\s\S]*padding-bottom:\s*2px\s*!important/);
assert.doesNotMatch(multieventFix, /Palacio Rioja/);
const releaseMatch = release.match(/const RELEASE = (\d+);/);
assert.ok(releaseMatch, "release-version.js must expose a numeric RELEASE");
assert.ok(Number(releaseMatch[1]) >= 122, "PWA release must include museum hours and multievent readability");

const gijon = JSON.parse(fs.readFileSync(path.join(app, "data/gijon/agenda_web.json"), "utf8"));
const venues = new Map();
for (const event of gijon.events || []) {
  const id = String(event?.primary_category?.id || event?.categories?.[0]?.id || "");
  if (!["exposiciones", "museos"].includes(id)) continue;
  const venue = String(event?.location?.venue || "").trim();
  if (venue) venues.set(venue, (venues.get(venue) || 0) + 1);
}
assert.ok([...venues.values()].some((count) => count >= 2), "Gijón must retain venues with multiple exhibitions");

console.log("Static grouping + venue identity + museum hours + readable multievent layout contract: OK");
