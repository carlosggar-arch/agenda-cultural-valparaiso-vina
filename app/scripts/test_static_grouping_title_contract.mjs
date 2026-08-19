import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { normalizePublicEventTitle } from "../public-title-normalizer.mjs";

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

const appJs = read("app.js");
const grouping = read("static-exhibition-groups.js");
const titleBootstrap = read("title-normalizer-bootstrap.js");
const compactCss = read("exhibition-compact.css");
const release = read("release-version.js");

assert.match(appJs, /title-normalizer-bootstrap\.js/);
assert.match(appJs, /static-exhibition-groups\.js/);
assert.doesNotMatch(appJs, /exhibition-venue-grouping|exhibition-gallery\.js|exhibition-compact-loader|presentation-normalizer\.js/);
assert.doesNotMatch(grouping, /MutationObserver|IntersectionObserver|getBoundingClientRect|offsetHeight|addEventListener\(["']scroll/);
assert.doesNotMatch(titleBootstrap, /MutationObserver|IntersectionObserver/);
assert.match(grouping, /MIN_GROUP_SIZE = 2/);
assert.match(grouping, /staticExhibitionSentinels/);
assert.match(compactCss, /\.event-grid\s*\{[^}]*align-items:\s*stretch\s*!important/s);
assert.match(compactCss, /\.event-grid\s*>\s*\.event-card\s*\{[^}]*align-self:\s*stretch\s*!important/s);
assert.doesNotMatch(compactCss, /align-items:\s*start\s*!important/);
assert.doesNotMatch(compactCss, /align-self:\s*start\s*!important/);
const releaseMatch = release.match(/const RELEASE = (\d+);/);
assert.ok(releaseMatch, "release-version.js must expose a numeric RELEASE");
assert.ok(Number(releaseMatch[1]) >= 114, "PWA release must not regress below v114");

const gijon = JSON.parse(fs.readFileSync(path.join(app, "data/gijon/agenda_web.json"), "utf8"));
const venues = new Map();
for (const event of gijon.events || []) {
  const id = String(event?.primary_category?.id || event?.categories?.[0]?.id || "");
  if (!["exposiciones", "museos"].includes(id)) continue;
  const venue = String(event?.location?.venue || "").trim();
  if (venue) venues.set(venue, (venues.get(venue) || 0) + 1);
}
assert.ok([...venues.values()].some((count) => count >= 2), "Gijón must retain venues with multiple exhibitions");

console.log("Static grouping + title normalization + row equalization contract: OK");
