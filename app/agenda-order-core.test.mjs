import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  agendaPresentationRank,
  compareAgendaOrder,
  compareAgendaSemanticPriority,
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
} = {}) {
  return {
    id,
    title,
    event_type: eventType,
    primary_category: { id: category, label: category },
    categories: [{ id: category, label: category }],
    location: { city, commune, venue: `${id} venue` },
    schedule: { mode: "dated", start, end, occurrences: [] },
  };
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

  const ordered = [...fixtures]
    .sort((a, b) => compareAgendaOrder(a, b, valpo, NOW))
    .map((item) => item.id);

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

test("top-level renderers share one agenda order authority", async () => {
  const guard = await readFile(new URL("./exhibition-presentation-guard.js", import.meta.url), "utf8");
  const app = await readFile(new URL("./app.js", import.meta.url), "utf8");
  const core = await readFile(new URL("./app-core.js", import.meta.url), "utf8");

  assert.doesNotMatch(guard, /\.style\.order\s*=/);
  assert.doesNotMatch(guard, /function\s+cityRank\b/);
  assert.match(app, /compareAgendaOrder/);
  assert.doesNotMatch(app, /compareTemporalPriority/);
  assert.match(core, /compareAgendaOrder/);
  assert.doesNotMatch(core, /function\s+sortEvents\b/);
  assert.doesNotMatch(core, /isLongExhibitionDuration/);
});
