import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  agendaPresentationRank,
  compareAgendaOrder,
  compareAgendaSemanticPriority,
  diversifySortedAgendaEvents,
} from "./agenda-order-core.mjs";
import { compareTemporalPriority } from "./temporal-priority-core.mjs";

const registry = JSON.parse(await readFile(new URL("./cities.json", import.meta.url), "utf8"));
const valpo = registry.cities.find((city) => city.id === "valparaiso");
const gijon = registry.cities.find((city) => city.id === "gijon");
const NOW = new Date("2026-08-22T12:00:00-04:00");

function event(id, {
  city = "Viña del Mar",
  commune = city,
  category = "musica",
  start = "2026-08-22T19:00:00-04:00",
  end = null,
  eventType = "event",
  title = id,
  venue = `${id} venue`,
  sourceName = "",
  organizer = "",
} = {}) {
  return {
    id,
    title,
    event_type: eventType,
    source_name: sourceName,
    organizer,
    primary_category: { id: category, label: category },
    categories: [{ id: category, label: category }],
    location: { city, commune, venue },
    schedule: { mode: "dated", start, end, occurrences: [] },
  };
}

function canonical(events, city = valpo, now = NOW) {
  return [...events].sort((a, b) => compareAgendaOrder(a, b, city, now));
}

test("Valpo presentation rank is category-neutral and area-only", () => {
  assert.equal(agendaPresentationRank(event("vina"), valpo), 0);
  assert.equal(agendaPresentationRank(event("valpo", { city: "Valparaíso" }), valpo), 1);
  assert.equal(agendaPresentationRank(event("other", { city: "Concón" }), valpo), 2);
  assert.equal(agendaPresentationRank(event("vina-expo", { category: "exposiciones" }), valpo), 0);
  assert.equal(agendaPresentationRank(event("valpo-museum", { city: "Valparaíso", category: "museos" }), valpo), 1);
  assert.equal(agendaPresentationRank(event("other-expo", { city: "Concón", category: "exposiciones" }), valpo), 2);
});

test("cities without presentation overrides keep shared temporal ordering", () => {
  const a = event("a", { city: "Gijón", start: "2026-08-22T20:00:00+02:00" });
  const b = event("b", { city: "Gijón", start: "2026-08-23T10:00:00+02:00" });
  assert.equal(agendaPresentationRank(a, gijon), 0);
  assert.equal(Math.sign(compareAgendaOrder(a, b, gijon, NOW)), Math.sign(compareTemporalPriority(a, b, gijon, NOW)));
});

test("temporal urgency outranks local area preference", () => {
  const todayOther = event("other-today", { city: "Concón", start: "2026-08-22T16:00:00-04:00" });
  const tomorrowVina = event("vina-tomorrow", { start: "2026-08-23T12:00:00-04:00" });

  assert.equal(agendaPresentationRank(todayOther, valpo), 2);
  assert.equal(agendaPresentationRank(tomorrowVina, valpo), 0);
  assert.ok(compareAgendaSemanticPriority(todayOther, tomorrowVina, valpo, NOW) < 0);
  assert.ok(compareAgendaOrder(todayOther, tomorrowVina, valpo, NOW) < 0);
});

test("local area preference only breaks a semantic tie", () => {
  const vina = event("z-vina", { start: "2026-08-23T12:00:00-04:00", title: "Z Viña" });
  const puerto = event("a-valpo", { city: "Valparaíso", start: "2026-08-23T12:00:00-04:00", title: "A Valparaíso" });

  assert.equal(compareAgendaSemanticPriority(vina, puerto, valpo, NOW), 0);
  assert.ok(compareAgendaOrder(vina, puerto, valpo, NOW) < 0);
});

test("category does not demote exhibitions when semantic priority is equal", () => {
  const concert = event("a-concert", {
    category: "musica",
    start: "2026-08-23T12:00:00-04:00",
    title: "A concierto",
  });
  const exhibition = event("b-expo", {
    category: "exposiciones",
    start: "2026-08-23T12:00:00-04:00",
    title: "B exposición",
  });

  assert.equal(agendaPresentationRank(concert, valpo), agendaPresentationRank(exhibition, valpo));
  assert.equal(compareAgendaSemanticPriority(concert, exhibition, valpo, NOW), 0);
  assert.ok(compareAgendaOrder(concert, exhibition, valpo, NOW) < 0);
});

test("canonical comparator exposes the new multi-city temporal-first order", () => {
  const fixtures = [
    event("valpo-tomorrow", { city: "Valparaíso", start: "2026-08-23T12:00:00-04:00" }),
    event("vina-tomorrow", { start: "2026-08-23T12:00:00-04:00" }),
    event("vina-today", { start: "2026-08-22T20:00:00-04:00" }),
    event("other-today", { city: "Concón", start: "2026-08-22T16:00:00-04:00" }),
    event("vina-expo", { category: "exposiciones", start: "2026-08-01", end: "2026-08-30" }),
    event("valpo-expo", { city: "Valparaíso", category: "museos", start: "2026-08-01", end: "2026-08-30" }),
    event("other-expo", { city: "Concón", category: "exposiciones", start: "2026-08-01", end: "2026-08-30" }),
  ];

  const ordered = canonical(fixtures).map((item) => item.id);

  assert.deepEqual(ordered, [
    "other-today",
    "vina-today",
    "vina-tomorrow",
    "valpo-tomorrow",
    "vina-expo",
    "valpo-expo",
    "other-expo",
  ]);
});

test("diversity pulls a nearby venue alternative before a fourth venue card", () => {
  const fixtures = [
    event("a1", { venue: "Sala A" }),
    event("a2", { venue: "Sala A" }),
    event("a3", { venue: "Sala A" }),
    event("a4", { venue: "Sala A" }),
    event("b1", { venue: "Sala B" }),
  ];
  const diversified = diversifySortedAgendaEvents(canonical(fixtures), valpo, NOW).map((item) => item.id);
  assert.deepEqual(diversified.slice(0, 4), ["a1", "a2", "a3", "b1"]);
});

test("diversity pulls another category before a fifth category card", () => {
  const fixtures = [
    event("a1", { venue: "V1", category: "musica" }),
    event("a2", { venue: "V2", category: "musica" }),
    event("a3", { venue: "V3", category: "musica" }),
    event("a4", { venue: "V4", category: "musica" }),
    event("a5", { venue: "V5", category: "musica" }),
    event("b1", { venue: "V6", category: "teatro" }),
  ];
  const diversified = diversifySortedAgendaEvents(canonical(fixtures), valpo, NOW).map((item) => item.id);
  assert.deepEqual(diversified.slice(0, 5), ["a1", "a2", "a3", "a4", "b1"]);
});

test("diversity also limits one source or institution when alternatives exist", () => {
  const fixtures = [
    event("a1", { venue: "V1", category: "musica", sourceName: "Institución A" }),
    event("a2", { venue: "V2", category: "teatro", sourceName: "Institución A" }),
    event("a3", { venue: "V3", category: "cine", sourceName: "Institución A" }),
    event("a4", { venue: "V4", category: "danza", sourceName: "Institución A" }),
    event("b1", { venue: "V5", category: "literatura", sourceName: "Institución B" }),
  ];
  const diversified = diversifySortedAgendaEvents(canonical(fixtures), valpo, NOW).map((item) => item.id);
  assert.deepEqual(diversified.slice(0, 4), ["a1", "a2", "a3", "b1"]);
});

test("diversity never crosses a temporal bucket boundary", () => {
  const today = [
    event("today-1", { venue: "Sala A", start: "2026-08-22T16:00:00-04:00" }),
    event("today-2", { venue: "Sala A", start: "2026-08-22T17:00:00-04:00" }),
    event("today-3", { venue: "Sala A", start: "2026-08-22T18:00:00-04:00" }),
    event("today-4", { venue: "Sala A", start: "2026-08-22T19:00:00-04:00" }),
  ];
  const tomorrow = event("tomorrow-alt", { venue: "Sala B", start: "2026-08-23T10:00:00-04:00" });
  const diversified = diversifySortedAgendaEvents(canonical([...today, tomorrow]), valpo, NOW).map((item) => item.id);
  assert.deepEqual(diversified.slice(0, 4), ["today-1", "today-2", "today-3", "today-4"]);
  assert.equal(diversified[4], "tomorrow-alt");
});

test("same bounded diversity policy works for Gijón without city-specific code", () => {
  const fixtures = [
    event("a1", { city: "Gijón", venue: "Sala A", start: "2026-08-22T18:00:00+02:00" }),
    event("a2", { city: "Gijón", venue: "Sala A", start: "2026-08-22T18:00:00+02:00" }),
    event("a3", { city: "Gijón", venue: "Sala A", start: "2026-08-22T18:00:00+02:00" }),
    event("a4", { city: "Gijón", venue: "Sala A", start: "2026-08-22T18:00:00+02:00" }),
    event("b1", { city: "Gijón", venue: "Sala B", start: "2026-08-22T18:00:00+02:00" }),
  ];
  const diversified = diversifySortedAgendaEvents(canonical(fixtures, gijon), gijon, NOW).map((item) => item.id);
  assert.deepEqual(diversified.slice(0, 4), ["a1", "a2", "a3", "b1"]);
});

test("top-level renderers share one agenda order authority", async () => {
  const guard = await readFile(new URL("./exhibition-presentation-guard.js", import.meta.url), "utf8");
  const app = await readFile(new URL("./app.js", import.meta.url), "utf8");
  const core = await readFile(new URL("./app-core.js", import.meta.url), "utf8");

  assert.doesNotMatch(guard, /\.style\.order\s*=/);
  assert.doesNotMatch(guard, /function\s+cityRank\b/);
  assert.match(app, /compareAgendaOrder/);
  assert.match(app, /diversifySortedAgendaEvents/);
  assert.doesNotMatch(app, /compareTemporalPriority/);
  assert.match(core, /compareAgendaOrder/);
  assert.doesNotMatch(core, /function\s+sortEvents\b/);
  assert.doesNotMatch(core, /isLongExhibitionDuration/);
});
