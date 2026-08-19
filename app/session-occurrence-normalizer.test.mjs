import assert from "node:assert/strict";
import { applyEventDataCorrections } from "./event-data-corrections.js";
import { normalizeSessionOccurrences } from "./session-occurrence-normalizer.js";

const baseStatus = { source_official: true, information_completeness: "complete" };
const cinemaBase = {
  event_type: "event",
  title: "Adolescencia, Sexo y Muerte en Camp Miasma",
  primary_category: { id: "cine", label: "Cine" },
  categories: [{ id: "cine", label: "Cine" }],
  location: { venue_id: "cinearte_vina", venue: "Cine Arte Viña del Mar", city: "Viña del Mar" },
  price: { is_free: false, currency: "CLP", min_amount: 4000, max_amount: 5500, display_text: "Entrada General: $5.500 · Estudiantes y Personas Mayores: $4.000" },
  source_id: "cinearte_vina",
  source_name: "Cine Arte Viña del Mar",
  links: { tickets: "https://www.passline.com/eventos/adolescencia-sexo-y-muerte-en-camp-miasma-cine-arte-vina-del-mar-543788" },
  public_status: baseStatus,
};

const dataset = {
  counts: { total: 6, events: 6, courses: 0, flexible_offers: 0, programs: 0 },
  events: [
    { ...cinemaBase, id: "film-13", schedule: { mode: "single", start: "2026-08-19T13:00:00-04:00", end: "2026-08-19T13:00:00-04:00", occurrences: [] } },
    { ...cinemaBase, id: "film-18", schedule: { mode: "single", start: "2026-08-19T18:00:00-04:00", end: "2026-08-19T18:00:00-04:00", occurrences: [] } },
    { ...cinemaBase, id: "film-25", schedule: { mode: "single", start: "2026-08-25T18:00:00-04:00", end: "2026-08-25T18:00:00-04:00", occurrences: [] } },
    {
      id: "pajareando",
      title: "Curso para Profes Pajareando Aprendo",
      event_type: "event",
      primary_category: { id: "cursos-talleres", label: "Cursos y talleres" },
      categories: [{ id: "cursos-talleres", label: "Cursos y talleres" }],
      location: { venue: "Museo Artequin Viña del Mar", city: "Viña del Mar" },
      source_url: "https://artequinvina.cl/",
      schedule: { mode: "multi_day", start: "2026-08-19T18:30:00-04:00", end: "2026-08-22", display_text: "2026-08-19 · 18:30, 20:00, 10:00, 14:00", occurrences: [] },
      price: { is_free: true, display_text: "Gratis" },
      public_status: baseStatus,
    },
    {
      id: "nebulosa",
      title: "Nebulosa Carina",
      event_type: "event",
      primary_category: { id: "exposiciones", label: "Exposiciones" },
      categories: [{ id: "exposiciones", label: "Exposiciones" }],
      location: { venue: "Sitio web Museo Baburizza", city: "Valparaíso" },
      source_url: "https://www.museobaburizza.cl/actividad/nebulosa-carina/",
      schedule: { mode: "multi_day", start: "2026-08-05T00:00:00-04:00", end: "2026-10-04T23:59:00-03:00", display_text: "2026-08-05 – 2026-10-04 · 00:00–23:59", occurrences: [] },
      price: { is_free: true, display_text: "Gratis" },
      public_status: baseStatus,
    },
    {
      id: "cumbias",
      title: "Las cumbias que escuchamos allá arriba",
      event_type: "event",
      primary_category: { id: "exposiciones", label: "Exposiciones" },
      categories: [{ id: "exposiciones", label: "Exposiciones" }],
      location: { venue: "Sala Blanca – Museo Baburizza", city: "Valparaíso" },
      source_url: "https://www.museobaburizza.cl/actividad/las-cumbias-que-escuchamos-alla-arriba/",
      schedule: { mode: "multi_day", start: "2026-08-14T10:00:00-04:00", end: "2026-10-04T18:00:00-03:00", display_text: "14-08-2026 · 10:00 – 04-10-2026 · 18:00", occurrences: [] },
      price: { is_free: null, display_text: "Consultar precio" },
      public_status: baseStatus,
    },
  ],
};

const normalized = normalizeSessionOccurrences(dataset);
assert.equal(normalized.events.length, 4);

const film = normalized.events.find((event) => event.title === cinemaBase.title);
assert.ok(film);
assert.equal(film.schedule.mode, "multi_session");
assert.deepEqual(film.schedule.occurrences.map((item) => item.start), [
  "2026-08-19T13:00:00-04:00",
  "2026-08-19T18:00:00-04:00",
  "2026-08-25T18:00:00-04:00",
]);

const pajareando = normalized.events.find((event) => event.id === "pajareando");
assert.equal(pajareando.title, "Pajareando Aprendo — curso para profes");
assert.deepEqual(pajareando.schedule.occurrences.map((item) => [item.start, item.end]), [
  ["2026-08-19T18:30:00-04:00", "2026-08-19T20:00:00-04:00"],
  ["2026-08-22T10:00:00-04:00", "2026-08-22T14:00:00-04:00"],
]);

const nebulosa = normalized.events.find((event) => event.id === "nebulosa");
assert.equal(nebulosa.schedule.start, "2026-08-06");
assert.equal(nebulosa.schedule.end, "2026-10-04");
assert.equal(nebulosa.schedule.opening_time, null);

const cumbias = normalized.events.find((event) => event.id === "cumbias");
assert.equal(cumbias.schedule.start, "2026-08-14");
assert.equal(cumbias.schedule.end, "2026-10-04");
assert.equal(cumbias.schedule.opening_time, "10:00");
assert.equal(cumbias.schedule.closing_time, "18:00");
assert.equal(cumbias.price.is_free, true);

const riojaInput = {
  counts: { total: 1, events: 1, courses: 0, flexible_offers: 0, programs: 0 },
  events: [{
    id: "mar-dulce-existing",
    title: "A veces un mar dulce",
    event_type: "event",
    primary_category: { id: "exposiciones", label: "Exposiciones" },
    categories: [{ id: "exposiciones", label: "Exposiciones" }],
    schedule: { mode: "dated", start: "2026-08-19T06:00:00-04:00", end: "2026-08-19T13:30:00-04:00", occurrences: [] },
    location: { venue: "Museo Palacio Rioja", city: "Viña del Mar" },
    price: { is_free: true, display_text: "Gratis" },
    links: { official: "https://visitavina.munivina.cl/actividad/exposicion-temporal-a-veces-un-mar-dulce/" },
    public_status: baseStatus,
  }],
};

const rioja = applyEventDataCorrections(riojaInput);
const riojaExhibitions = rioja.events.filter((event) =>
  event.primary_category?.id === "exposiciones" && event.location?.venue === "Museo Palacio Rioja"
);
const riojaTitles = new Set(riojaExhibitions.map((event) => event.title));
assert.equal(riojaTitles.has("A veces un mar dulce"), true);
assert.equal(riojaTitles.has("Muestra temporal // Mis objetos, mi patrimonio"), true);
assert.equal(riojaTitles.has("Visita guiada exposición // “A veces un mar dulce”"), true);
assert.equal(riojaExhibitions.find((event) => event.id === "mar-dulce-existing")?.schedule?.end, "2026-08-30");
assert.equal(riojaExhibitions.find((event) => event.id === "mar-dulce-existing")?.schedule?.opening_hours?.display_text, "Martes a domingo · 10:00–17:30");
const decadencia = rioja.events.find((event) => event.id === "agenda_rioja_20260827_decadencia");
assert.equal(decadencia?.primary_category?.id, "otros");
assert.equal(decadencia?.schedule?.start, "2026-08-27T18:00:00-04:00");
assert.equal(decadencia?.schedule?.end, "2026-08-27T20:00:00-04:00");

console.log("SESSION_OCCURRENCE_NORMALIZER_OK");
