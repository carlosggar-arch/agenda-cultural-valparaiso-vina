import assert from "node:assert/strict";
import { isLongFormationCycle, normalizeFormationCycles } from "./formation-cycle-classifier.js";

const formationCycle = {
  id: "agenda_fd3ddae09e1576497c5cb7d7",
  title: "Fortalece tus herramientas para la gestión cultural",
  event_type: "event",
  primary_category: { id: "cursos-talleres-campus", label: "Cursos, talleres y campus" },
  categories: [{ id: "cursos-talleres-campus", label: "Cursos, talleres y campus" }],
  schedule: {
    mode: "multi_day",
    start: "2026-08-18T18:00:00-04:00",
    end: "2026-11-14",
    display_text: "2026-08-18 – 2026-11-14",
    occurrences: [],
    opening_time: "10:00",
    closing_time: "17:30",
    opening_hours: { mode: "weekly", open_weekdays: [1, 2, 3, 4, 5] },
    hours_confidence: "source_schedule_pair",
  },
  description: "El Municipio de Cuidados de Viña del Mar te invita a participar en el II Ciclo de Formación Cultural, un espacio pensado para gestores, artistas y agentes culturales.",
  tags: ["formación", "taller"],
  editorial: { venue_hours_enriched: true },
};

assert.equal(isLongFormationCycle(formationCycle), true, "a long formation cycle without explicit sessions must not behave like a daily event");

const legacyFormationCycle = {
  ...formationCycle,
  id: "legacy-formation-cycle",
  primary_category: { id: "formacion-taller", label: "Formación / taller" },
  categories: [{ id: "formacion-taller", label: "Formación / taller" }],
};
assert.equal(isLongFormationCycle(legacyFormationCycle), true, "legacy formation categories must remain compatible during normalization");

const normalized = normalizeFormationCycles({ events: [formationCycle] });
assert.equal(normalized.events[0].event_type, "program");
assert.equal(normalized.events[0].editorial.reason, "long_formation_cycle_not_daily_event");
assert.equal(normalized.events[0].schedule.opening_time, undefined, "museum opening hours must not be presented as course session hours");
assert.equal(normalized.events[0].schedule.opening_hours, undefined);

const shortWorkshop = {
  ...formationCycle,
  id: "short-workshop",
  schedule: { ...formationCycle.schedule, start: "2026-08-20T10:00:00-04:00", end: "2026-08-22" },
};
assert.equal(isLongFormationCycle(shortWorkshop), false, "a genuine short multi-day workshop must remain a dated event");

const exhibition = {
  ...formationCycle,
  id: "exhibition",
  primary_category: { id: "exposiciones", label: "Exposiciones" },
  categories: [{ id: "exposiciones", label: "Exposiciones" }],
  description: "Exposición abierta durante varios meses.",
};
assert.equal(isLongFormationCycle(exhibition), false, "long exhibitions must not be reclassified as formation programs");

console.log("FORMATION_CYCLE_CLASSIFIER_OK");
