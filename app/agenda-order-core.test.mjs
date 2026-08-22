import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { agendaPresentationRank, compareAgendaOrder } from "./agenda-order-core.mjs";
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
} = {}) {
  return {
    id,
    title: id,
    event_type: eventType,
    primary_category: { id: category, label: category },
    categories: [{ id: category, label: category }],
    location: { city, commune, venue: `${id} venue` },
    schedule: { mode: "dated", start, end, occurrences: [] },
  };
}

function legacyPresentationRank(item) {
  const place = `${item?.location?.city || ""} ${item?.location?.commune || ""}`
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
  const cityRank = place.includes("vina del mar") || /\bvina\b/.test(place)
    ? 0
    : place.includes("valparaiso")
      ? 1
      : 2;
  const category = String(item?.primary_category?.id || item?.categories?.[0]?.id || "");
  const exhibitionRank = ["exposiciones", "museos"].includes(category) ? 100 : 0;
  return cityRank + exhibitionRank;
}

function legacyVisibleComparator(a, b) {
  const presentationDiff = legacyPresentationRank(a) - legacyPresentationRank(b);
  if (presentationDiff) return presentationDiff;
  return compareTemporalPriority(a, b, valpo, NOW);
}

test("Valpo presentation ranks preserve the removed CSS order exactly", () => {
  assert.equal(agendaPresentationRank(event("vina"), valpo), 0);
  assert.equal(agendaPresentationRank(event("valpo", { city: "Valparaíso" }), valpo), 1);
  assert.equal(agendaPresentationRank(event("other", { city: "Concón" }), valpo), 2);
  assert.equal(agendaPresentationRank(event("vina-expo", { category: "exposiciones" }), valpo), 100);
  assert.equal(agendaPresentationRank(event("valpo-museum", { city: "Valparaíso", category: "museos" }), valpo), 101);
  assert.equal(agendaPresentationRank(event("other-expo", { city: "Concón", category: "exposiciones" }), valpo), 102);
});

test("cities without presentation overrides keep pure temporal ordering", () => {
  const a = event("a", { city: "Gijón", start: "2026-08-22T20:00:00+02:00" });
  const b = event("b", { city: "Gijón", start: "2026-08-23T10:00:00+02:00" });
  assert.equal(agendaPresentationRank(a, gijon), 0);
  assert.equal(Math.sign(compareAgendaOrder(a, b, gijon, NOW)), Math.sign(compareTemporalPriority(a, b, gijon, NOW)));
});

test("within one presentation rank temporal-priority-core remains authoritative", () => {
  const a = event("today", { start: "2026-08-22T18:00:00-04:00" });
  const b = event("tomorrow", { start: "2026-08-23T18:00:00-04:00" });
  assert.equal(Math.sign(compareAgendaOrder(a, b, valpo, NOW)), Math.sign(compareTemporalPriority(a, b, valpo, NOW)));
});

test("C1 canonical comparator is A-equivalent to the legacy final visible order", () => {
  const fixtures = [
    event("valpo-tomorrow", { city: "Valparaíso", start: "2026-08-23T12:00:00-04:00" }),
    event("vina-tomorrow", { start: "2026-08-23T12:00:00-04:00" }),
    event("vina-today", { start: "2026-08-22T20:00:00-04:00" }),
    event("other-today", { city: "Concón", start: "2026-08-22T16:00:00-04:00" }),
    event("vina-expo", { category: "exposiciones", start: "2026-08-01", end: "2026-08-30" }),
    event("valpo-expo", { city: "Valparaíso", category: "museos", start: "2026-08-01", end: "2026-08-30" }),
    event("other-expo", { city: "Concón", category: "exposiciones", start: "2026-08-01", end: "2026-08-30" }),
  ];

  const before = [...fixtures].sort(legacyVisibleComparator).map((item) => item.id);
  const after = [...fixtures].sort((a, b) => compareAgendaOrder(a, b, valpo, NOW)).map((item) => item.id);
  assert.deepEqual(after, before);
});

test("exhibition presentation guard no longer owns CSS order", async () => {
  const guard = await readFile(new URL("./exhibition-presentation-guard.js", import.meta.url), "utf8");
  const app = await readFile(new URL("./app.js", import.meta.url), "utf8");
  assert.doesNotMatch(guard, /\.style\.order\s*=/);
  assert.match(app, /compareAgendaOrder/);
  assert.doesNotMatch(app, /compareTemporalPriority/);
});
