import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { applyEventDataCorrections } from "./event-data-corrections.js";
import { mergeRepeatedExhibitionVisits, normalizeSessionOccurrences } from "./session-occurrence-normalizer.js";
import { eventMatchesCanonicalSection } from "./public-selection-core.mjs";
import { removeExpiredDatedEvents } from "./runtime-past-event-guard.mjs";
import { normalizeEventScheduleContract } from "./schedule-contract.mjs";
import { formatSchedule } from "../assets/event-schedule-display.mjs";
import { sessionScheduleLabelForDate } from "./today-session-presentation.mjs";
import { groupedScheduleLabel } from "./public-presentation-rules.mjs";
import { normalizeAgendaTitles } from "./title-normalizer-bootstrap.js";
import { buildEventReferenceIndex } from "./event-reference-index.mjs";
import { findEventById } from "../assets/agenda-core.mjs";
import { buildReminderIcs, reminderOptionsForEvent } from "../assets/favorites-reminders.mjs";
import { favoritesForCity, saveFavorite } from "../assets/favorites-core.mjs";
import { buildMyPlansSection } from "../assets/favorites-view.mjs";
import { clearAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs";

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

const visitDates = ["2026-10-17", "2026-10-18", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"];
function exhibitionVisit(day) {
  return {
    id: `visit-${day}`,
    title: "La Playa: todo tiempo pasado fue mejor",
    event_type: "event",
    primary_category: { id: "exposiciones", label: "Exposiciones" },
    categories: [{ id: "exposiciones", label: "Exposiciones" }],
    source_id: "museo_palacio_rioja",
    source_url: "https://visitavina.munivina.cl/actividades/",
    location: { venue_id: "museo-palacio-rioja", venue: "Museo Palacio Rioja", city: "Viña del Mar" },
    price: { is_free: true, min_amount: 0, max_amount: 0, currency: "CLP", display_text: "Gratis" },
    public_status: { source_official: true, cancelled: false, sold_out: null, registration_open: null, registration_closed: null, price_confirmed: true },
    links: { official: `https://visitavina.munivina.cl/actividad/muestra-temporal-mis-objetos-mi-patrimonio-2-805-387/?occurrence=${day}`, tickets: null, registration: null },
    schedule: { mode: "dated", timezone: "America/Santiago", start: `${day}T10:00:00-03:00`, end: `${day}T17:30:00-03:00`, opening_time: "10:00", closing_time: "17:30", occurrences: [] },
  };
}
const visitCity = { id: "valparaiso", timezone: "America/Santiago", locale: "es-CL" };
const visitNow = new Date("2026-10-17T12:00:00-03:00");

test("one exhibition retains fourteen exact advertised visit windows and original identities", () => {
  const input = visitDates.map(exhibitionVisit);
  const before = structuredClone(input);
  const merged = mergeRepeatedExhibitionVisits(input);
  assert.equal(merged.length, 1);
  assert.equal(merged[0].id, input[0].id);
  assert.deepEqual(merged[0].schedule.occurrences, input.map((event) => ({ start: event.schedule.start, end: event.schedule.end })));
  assert.deepEqual(merged[0].editorial.exhibition_visits.source_event_ids, input.map((event) => event.id));
  assert.deepEqual(merged[0].editorial.exhibition_visits.sources.map((item) => item.url), input.map((event) => event.links.official));
  assert.deepEqual(input, before, "raw source events must not be mutated");
  assert.deepEqual(mergeRepeatedExhibitionVisits([...input].reverse()), merged, "same source dates yield a stable representative and order");
});

test("exhibition visit normalization is idempotent and updates runtime counts", () => {
  const input = { events: visitDates.map(exhibitionVisit), counts: { total: 14, events: 14 } };
  const result = normalizeSessionOccurrences(input);
  assert.equal(result.counts.total, 1);
  assert.equal(result.counts.events, 1);
  assert.equal(normalizeSessionOccurrences(result), result);
});

test("normalized exhibition references resolve every original child link with its own date and URL", () => {
  const visits = visitDates.map(exhibitionVisit);
  const model = JSON.parse(JSON.stringify(normalizeSessionOccurrences({ events: visits })));
  const index = buildEventReferenceIndex(model.events);
  assert.equal(model.events.length, 1, "reference aliases must not create additional cards");
  assert.equal(index.size, 14);
  assert.equal(index.get(visits[0].id), model.events[0], "the existing representative opens the full exhibition card");
  for (const original of visits.slice(1)) {
    const resolved = findEventById(model.events, original.id);
    assert.equal(resolved.id, original.id);
    assert.deepEqual(resolved.schedule, original.schedule);
    assert.equal(resolved.links.official, original.links.official);
    assert.deepEqual(index.get(original.id), resolved);
    const calendar = buildReminderIcs({ city: visitCity.id, event: resolved, now: visitNow });
    const stamp = (value) => new Date(value).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
    assert.ok(calendar.includes(`DTSTART:${stamp(original.schedule.start)}`));
    assert.ok(calendar.includes(`DTEND:${stamp(original.schedule.end)}`));
  }
  assert.equal(findEventById(model.events, "not-a-retained-id"), null);
  const explicit = { ...visits[1], title: "An independent canonical event" };
  assert.equal(buildEventReferenceIndex([...model.events, explicit]).get(explicit.id), explicit,
    "aliases must never shadow a canonical event");
});

test("saved child visits remain resolved in Mis planes without changing their stored identity", () => {
  const visits = visitDates.map(exhibitionVisit);
  const model = normalizeSessionOccurrences({ events: visits });
  const originalWindow = globalThis.window;
  const originalDocument = globalThis.document;
  const stored = new Map();
  const storage = { getItem: (key) => stored.get(key) || null, setItem: (key, value) => stored.set(key, value) };
  const nodes = [];
  globalThis.window = { localStorage: storage };
  globalThis.document = { createElement(tag) {
    const node = { tag, dataset: {}, children: [], append(...children) { this.children.push(...children); }, setAttribute() {}, addEventListener() {} };
    nodes.push(node);
    return node;
  } };
  try {
    const original = visits[1];
    const url = `https://example.org/evento/${visitCity.id}/${original.id}/`;
    saveFavorite({ city: visitCity.id, id: original.id, title: original.title, url, savedAt: visitNow.toISOString() }, storage);
    const before = [...stored.entries()];
    buildMyPlansSection({ city: visitCity.id, locale: visitCity.locale, eventMap: buildEventReferenceIndex(model.events), eventPageHref: () => null });
    const row = nodes.find((node) => node.className === "my-plan-row");
    assert.equal(row.dataset.eventId, original.id);
    assert.equal(nodes.find((node) => node.className === "my-plan-date").textContent, "18 oct");
    assert.ok(nodes.some((node) => node.tag === "small" && node.textContent.includes("Museo Palacio Rioja")));
    assert.ok(nodes.some((node) => node.tag === "a" && node.href === url));
    assert.ok(nodes.every((node) => node.textContent !== "Ya no aparece en la agenda actual"));
    assert.deepEqual([...stored.entries()], before);
    assert.equal(favoritesForCity("gijon", storage).length, 0);
  } finally {
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
    if (originalDocument === undefined) delete globalThis.document;
    else globalThis.document = originalDocument;
  }
});

test("an exhibition reminder retains one visit duration rather than the full date span", () => {
  const [event] = mergeRepeatedExhibitionVisits(visitDates.map(exhibitionVisit));
  const calendar = buildReminderIcs({ city: visitCity.id, event, now: new Date("2026-10-16T12:00:00-03:00") });
  assert.match(calendar, /DTSTART:20261017T130000Z/);
  assert.match(calendar, /DTEND:20261017T203000Z/);
  assert.doesNotMatch(calendar, /DTEND:20261101/);
});

test("exhibition reminders choose the same next visit for options and calendar after today's start", () => {
  const visits = visitDates.map(exhibitionVisit);
  const [event] = mergeRepeatedExhibitionVisits(visits);
  const now = new Date("2026-10-17T15:00:00Z");
  assert.deepEqual(reminderOptionsForEvent(event, now).map((option) => option.id), ["2h"]);
  const pageUrl = `https://example.org/evento/${visitCity.id}/${event.id}/`;
  const calendar = buildReminderIcs({ city: visitCity.id, event, now, lead: "2h", pageUrl });
  assert.match(calendar, /DTSTART:20261018T130000Z/);
  assert.match(calendar, /DTEND:20261018T203000Z/);
  assert.ok(calendar.includes(`URL:https://example.org/evento/${visitCity.id}/${visits[1].id}/`));
  assert.ok(calendar.includes(`UID:${visitCity.id}-${visits[1].id}@vivamos.local`));
  const queryCalendar = buildReminderIcs({ city: visitCity.id, event, now, pageUrl: `https://example.org/?evento=${event.id}` });
  assert.ok(queryCalendar.includes(`URL:https://example.org/?evento=${visits[1].id}`));
  const officialCalendar = buildReminderIcs({ city: visitCity.id, event, now });
  assert.ok(officialCalendar.includes(`URL:${visits[1].links.official}`));
  const ended = new Date("2026-11-02T15:00:00Z");
  assert.deepEqual(reminderOptionsForEvent(event, ended), []);
  assert.equal(buildReminderIcs({ city: visitCity.id, event, now: ended }), null);
  const child = findEventById([event], visits[1].id);
  const afterChild = new Date("2026-10-19T15:00:00Z");
  assert.deepEqual(reminderOptionsForEvent(child, afterChild), [], "a saved child visit must not move to a later day");
  const childCalendar = buildReminderIcs({ city: visitCity.id, event: child, now: afterChild, pageUrl: "https://example.org/original-child-url" });
  assert.match(childCalendar, /DTSTART:20261018T130000Z/);
  assert.match(childCalendar, /URL:https:\/\/example.org\/original-child-url/);
});

test("exhibition filters use advertised dates, never the continuous bounding interval", () => {
  const [event] = mergeRepeatedExhibitionVisits(visitDates.map(exhibitionVisit));
  assert.equal(eventMatchesCanonicalSection(event, "hoy", visitCity, visitNow), true);
  assert.equal(eventMatchesCanonicalSection(event, "manana", visitCity, visitNow), true);
  assert.equal(eventMatchesCanonicalSection(event, "fin-de-semana", visitCity, visitNow), true);
  for (const day of visitDates) {
    assert.equal(eventMatchesCanonicalSection(event, "personalizado", visitCity, visitNow, { from: day, to: day }), true, day);
  }
  for (const day of ["2026-10-16", "2026-10-19", "2026-10-26", "2026-11-02"]) {
    assert.equal(eventMatchesCanonicalSection(event, "personalizado", visitCity, visitNow, { from: day, to: day }), false, day);
  }
});

test("expired exhibition windows are pruned without losing future dates or original IDs", () => {
  const [event] = mergeRepeatedExhibitionVisits(visitDates.map(exhibitionVisit));
  const now = new Date("2026-10-18T00:05:00-03:00");
  const result = removeExpiredDatedEvents({ events: [event] }, { now, timeZone: visitCity.timezone });
  assert.equal(result.events.length, 1);
  assert.equal(result.events[0].schedule.occurrences.length, 13);
  assert.equal(result.events[0].id, event.id);
  assert.equal(result.events[0].editorial.exhibition_visits.source_event_ids.length, 14);
  assert.equal(eventMatchesCanonicalSection(result.events[0], "hoy", visitCity, now), true);
  assert.equal(eventMatchesCanonicalSection(result.events[0], "manana", visitCity, now), false);
  assert.equal(removeExpiredDatedEvents({ events: [event] }, { now: new Date("2026-11-02T00:05:00-03:00"), timeZone: visitCity.timezone }).events.length, 0);
});

test("different exhibitions, venues, sources, prices, timezones and public states stay distinct", () => {
  const changes = [
    (event) => { event.title = "Otra muestra"; },
    (event) => { event.location.venue_id = "otra-sala"; },
    (event) => { event.location.city = "Gijón"; },
    (event) => { event.source_id = "otro-museo"; },
    (event) => { event.price.min_amount = 1000; },
    (event) => { event.schedule.timezone = "Europe/Madrid"; },
    (event) => { event.primary_category.id = "cine"; },
    (event) => { event.event_type = "course"; },
    (event) => { event.links.official = event.links.official.replace("2-805-387", "otra-exposicion"); },
    (event) => { event.links.official += "&edition=other"; },
    (event) => { event.links.tickets = "https://example.org/ticket"; },
    (event) => { event.public_status.cancelled = true; },
    (event) => { event.public_status.sold_out = true; },
    (event) => { event.public_status.registration_closed = true; },
  ];
  for (const change of changes) {
    const first = exhibitionVisit(visitDates[0]);
    const second = exhibitionVisit(visitDates[1]);
    change(second);
    const input = [first, second];
    assert.equal(mergeRepeatedExhibitionVisits(input), input, String(change));
  }
});

test("unproven occurrence identities and incompatible schedules are not consolidated", () => {
  const changes = [
    (event) => { event.links.official = event.source_url; },
    (event) => { event.links.official = `${event.source_url}?occurrence=${visitDates[1]}`; },
    (event) => { event.links.official += `&occurrence=${visitDates[1]}`; },
    (event) => { event.links.official = event.links.official.replace(visitDates[1], "2026-10-19"); },
    (event) => { event.schedule.opening_time = "09:00"; },
    (event) => { event.schedule.start = event.schedule.start.replace("-03:00", "Z"); },
    (event) => { event.schedule.end = "2026-10-19T17:30:00-03:00"; },
    (event) => { event.schedule.occurrences = [{ start: event.schedule.start, end: event.schedule.end }]; },
    (event) => { event.public_status.source_official = false; },
    (event) => { event.source_id = ""; },
  ];
  for (const change of changes) {
    const input = [exhibitionVisit(visitDates[0]), exhibitionVisit(visitDates[1])];
    change(input[1]);
    assert.equal(mergeRepeatedExhibitionVisits(input), input, String(change));
  }
  const sameDay = [exhibitionVisit(visitDates[0]), { ...exhibitionVisit(visitDates[0]), id: "another-same-day" }];
  assert.equal(mergeRepeatedExhibitionVisits(sameDay), sameDay);
});

test("guided visits, exhibition openings and cinema retain their session identity", () => {
  for (const title of ["Visita guiada a La Playa", "Inauguración de La Playa", "Taller de fotografía en La Playa"]) {
    const input = visitDates.slice(0, 2).map((day) => ({ ...exhibitionVisit(day), title }));
    assert.equal(mergeRepeatedExhibitionVisits(input), input, title);
  }
  const guided = visitDates.slice(0, 2).map((day) => ({ ...exhibitionVisit(day), title: "Visita guiada: “La Playa”" }));
  const titled = normalizeAgendaTitles({ events: guided });
  assert.equal(titled.events[0].title, "La Playa");
  assert.equal(mergeRepeatedExhibitionVisits(titled.events), titled.events, "stripping the generic title prefix must not erase guided-visit identity");
  const cinema = visitDates.slice(0, 2).map((day) => ({ ...exhibitionVisit(day), primary_category: { id: "cine" } }));
  assert.equal(mergeRepeatedExhibitionVisits(cinema), cinema);
});

test("exhibition presentation shows available dates, range and hours without inventing an exhibition period", () => {
  const [merged] = mergeRepeatedExhibitionVisits(visitDates.map(exhibitionVisit));
  const event = normalizeEventScheduleContract(merged);
  const options = { locale: "es-CL", timezone: visitCity.timezone, now: visitNow, referenceDate: "2026-10-17" };
  const label = formatSchedule(event.schedule, options);
  assert.match(label, /^Fechas disponibles:/);
  assert.match(label, /17.*oct.*1.*nov/);
  assert.match(label, /10:00–17:30/);
  assert.match(label, /Días: 17–18, 20–25, 27–31 oct/);
  assert.match(label, /; 1 nov/);
  assert.doesNotMatch(label, /19|26|En exhibición|Cerrado/);
  assert.equal(groupedScheduleLabel(event, options), label);
  assert.equal(sessionScheduleLabelForDate(event, options), null, "visit windows are not a single selected-day function");
  const monday = { ...options, referenceDate: "2026-10-19" };
  assert.equal(formatSchedule(event.schedule, monday), label, "do not infer closure or opening from a missing advertised date");
});

test("the APP schedule owner keeps the shared exhibition date list and hours", async () => {
  const originalWindow = globalThis.window;
  const originalDocument = globalThis.document;
  globalThis.window = { addEventListener() {} };
  globalThis.document = { addEventListener() {}, documentElement: { dataset: {} }, querySelectorAll() { return []; } };
  try {
    const { scheduleForEventDisplay, exhibitionVisitHoursForDisplay } = await import("./schedule-display.js");
    const [event] = mergeRepeatedExhibitionVisits(visitDates.map(exhibitionVisit));
    const options = { locale: "es-CL", timezone: visitCity.timezone, now: visitNow, referenceDate: "2026-10-17" };
    assert.equal(scheduleForEventDisplay(event, options), formatSchedule(event.schedule, options));
    assert.equal(exhibitionVisitHoursForDisplay(event, options), null, "do not duplicate exact hours with a generic venue-hours label");
    await Promise.resolve();
  } finally {
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
    if (originalDocument === undefined) delete globalThis.document;
    else globalThis.document = originalDocument;
  }
});

test("the real Mis planes page reloads grouped and child favorites with precise next-visit calendars", async () => {
  const names = ["window", "document", "location", "localStorage", "fetch", "addEventListener", "Date", "URL", "caches", "CustomEvent"];
  const originals = new Map(names.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  const NativeDate = Date;
  const NativeURL = URL;
  const now = new NativeDate("2026-10-17T15:00:00Z");
  const visits = visitDates.map(exhibitionVisit);
  const stored = new Map();
  const storage = { getItem: (key) => stored.get(key) || null, setItem: (key, value) => stored.set(key, value) };
  for (const event of visits.slice(0, 2)) {
    saveFavorite({ city: visitCity.id, id: event.id, title: event.title, url: `https://example.org/evento/${visitCity.id}/${event.id}/`, savedAt: now.toISOString() }, storage);
  }
  const savedBefore = [...stored.entries()];
  class Element {
    constructor(tag) { this.tag = tag; this.dataset = {}; this.style = {}; this.children = []; this.listeners = {}; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute() {}
    addEventListener(name, handler) { this.listeners[name] = handler; }
    click() {}
    remove() {}
  }
  const walk = (node) => [node, ...(node.children || []).flatMap(walk)];
  const main = new Element("main");
  const head = new Element("head");
  const generatedCalendars = [];
  const requestedDatasets = [];
  let processedCacheOpens = 0;
  try {
    globalThis.Date = class extends NativeDate {
      constructor(...args) { super(...(args.length ? args : [now.getTime()])); }
      static now() { return now.getTime(); }
    };
    globalThis.URL = class extends NativeURL {
      static createObjectURL(blob) { generatedCalendars.push(blob); return "blob:exhibition-reminder-test"; }
      static revokeObjectURL() {}
    };
    globalThis.window = { localStorage: storage, dispatchEvent() {}, setTimeout() {} };
    globalThis.localStorage = storage;
    globalThis.location = { href: "https://example.org/app/mis-planes.html?city=valparaiso" };
    globalThis.addEventListener = () => {};
    globalThis.CustomEvent ||= class { constructor(type, init) { this.type = type; this.detail = init?.detail; } };
    globalThis.caches = { open() { processedCacheOpens += 1; throw new Error("standalone plans must not create an unversioned processed cache"); } };
    globalThis.document = {
      documentElement: { dataset: {} }, head, body: new Element("body"),
      createElement: (tag) => new Element(tag),
      querySelector(selector) {
        if (selector === "[data-my-plans-page]") return main;
        if (selector === "[data-place]") return new Element("small");
        return head.children.find((node) => node.dataset.favoritesStyles) || null;
      },
      querySelectorAll: () => [],
    };
    globalThis.fetch = async (input) => {
      const url = String(input);
      if (url.endsWith("/cities.json")) return { ok: true, json: async () => ({ schema_version: "1.0.0", default_city: visitCity.id, cities: [{ ...visitCity, label: "Valparaíso / Viña del Mar", dataset: "./fixture-exhibition.json" }] }) };
      assert.equal(url, "./fixture-exhibition.json", "the real page must use only its canonical city dataset");
      requestedDatasets.push(url);
      return { ok: true, json: async () => structuredClone({ schema_version: "1.0.0", events: visits, counts: { total: 14, events: 14 } }) };
    };
    const page = new NativeURL("./mis-planes.html", import.meta.url);
    const inlineModule = readFileSync(page, "utf8").match(/<script type="module">([\s\S]*?)<\/script>/)[1];
    const runnable = inlineModule.replace(/from"([^"]+)"/g, (_, specifier) => `from${JSON.stringify(new NativeURL(specifier, page).href)}`);
    const moduleUrl = `data:text/javascript;base64,${Buffer.from(runnable).toString("base64")}`;
    for (const reload of [0, 1]) {
      await import(`${moduleUrl}#reload-${reload}`);
      const rows = walk(main).filter((node) => node.className === "my-plan-row");
      assert.equal(rows.length, 2);
      for (const original of visits.slice(0, 2)) {
        const row = rows.find((node) => node.dataset.eventId === original.id);
        assert.ok(row, original.id);
        const reminder = walk(row).find((node) => node.className === "my-plan-reminder-option" && node.textContent === "2 horas antes");
        assert.ok(reminder, "both the newly grouped favorite and the retained child must still offer the next valid reminder after reload");
        reminder.listeners.click({ preventDefault() {}, stopPropagation() {} });
        const calendar = await generatedCalendars.at(-1).text();
        assert.match(calendar, /DTSTART:20261018T130000Z/);
        assert.match(calendar, /DTEND:20261018T203000Z/);
        assert.ok(calendar.includes(`UID:${visitCity.id}-${visits[1].id}@vivamos.local`));
        assert.ok(calendar.includes(`URL:https://example.org/evento/${visitCity.id}/${visits[1].id}/`));
      }
      assert.deepEqual([...stored.entries()], savedBefore, "loading and reloading must preserve every stored favorite identity");
    }
    assert.equal(requestedDatasets.length, 2, "each page load has one dataset owner");
    assert.equal(processedCacheOpens, 0);
  } finally {
    clearAgendaRuntimeSnapshot();
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  }
});
