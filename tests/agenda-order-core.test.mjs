import test from "node:test";
import assert from "node:assert/strict";

import {
  agendaPresentationRank,
  compareAgendaOrder,
} from "../app/agenda-order-core.mjs";

const now = new Date("2026-08-21T12:00:00Z");

const valpo = {
  timezone: "America/Santiago",
  locale: "es-CL",
  areas: [
    { id: "todos", match: [] },
    { id: "valparaiso", match: ["valparaiso"] },
    { id: "vina", match: ["vina del mar", "vina"] },
  ],
  presentation_order: {
    area_weights: { vina: 0, valparaiso: 1 },
    default_area_weight: 2,
  },
};

const gijon = {
  timezone: "Europe/Madrid",
  locale: "es-ES",
  areas: [],
};

function event(id, start, { city = "Viña del Mar", category = "musica", title = id } = {}) {
  return {
    id,
    title,
    event_type: "event",
    location: { city },
    primary_category: { id: category, label: category },
    categories: [{ id: category, label: category }],
    schedule: {
      mode: "dated",
      start,
      end: null,
      start_confidence: "explicit",
      occurrences: [],
    },
  };
}

test("temporal urgency outranks local area preference", () => {
  const todayValpo = event("today-valpo", "2026-08-21T20:00:00-04:00", { city: "Valparaíso" });
  const saturdayVina = event("saturday-vina", "2026-08-22T18:00:00-04:00", { city: "Viña del Mar" });

  assert.equal(agendaPresentationRank(todayValpo, valpo), 1);
  assert.equal(agendaPresentationRank(saturdayVina, valpo), 0);
  assert.ok(compareAgendaOrder(todayValpo, saturdayVina, valpo, now) < 0);
});

test("category does not bias ordering when all categories are visible", () => {
  const exhibition = event("expo", "2026-08-22T18:00:00-04:00", {
    city: "Viña del Mar",
    category: "exposiciones",
    title: "B exposición",
  });
  const concert = event("concert", "2026-08-22T18:00:00-04:00", {
    city: "Viña del Mar",
    category: "musica",
    title: "A concierto",
  });

  assert.equal(agendaPresentationRank(exhibition, valpo), agendaPresentationRank(concert, valpo));
  assert.ok(compareAgendaOrder(concert, exhibition, valpo, now) < 0);
});

test("local area preference is only a tie-break between semantic equals", () => {
  const vina = event("vina", "2026-08-22T18:00:00-04:00", { city: "Viña del Mar", title: "Z Viña" });
  const puerto = event("valpo", "2026-08-22T18:00:00-04:00", { city: "Valparaíso", title: "A Valparaíso" });

  assert.ok(compareAgendaOrder(vina, puerto, valpo, now) < 0);
});

test("cities without presentation policy use the same shared temporal semantics", () => {
  const today = event("today", "2026-08-21T20:00:00+02:00", { city: "Gijón" });
  const tomorrow = event("tomorrow", "2026-08-22T20:00:00+02:00", { city: "Gijón" });

  assert.equal(agendaPresentationRank(today, gijon), 0);
  assert.ok(compareAgendaOrder(today, tomorrow, gijon, now) < 0);
});
