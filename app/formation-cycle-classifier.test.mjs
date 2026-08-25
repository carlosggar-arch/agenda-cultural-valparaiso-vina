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

// Regression: title cleanup happens before formation lifecycle normalization.
// Once the presentation prefix has been removed, unrelated records must retain
// the category already resolved from their canonical source title/evidence.
const matriarcasAfterTitleCleanup = {
  id: "agenda_9007884dd819ed9a575ebda9",
  title: "Matriarcas: Poesía, Papel y Tinta",
  original_title: 'Teatro "Matriarcas: Poesía, Papel y Tinta"',
  event_type: "event",
  primary_category: { id: "teatro", label: "Teatro y danza" },
  categories: [{ id: "teatro", label: "Teatro y danza" }],
  schedule: { mode: "single", start: "2026-08-29T19:00:00-04:00", end: "2026-08-29T19:00:00-04:00", occurrences: [] },
  description: "Una propuesta escénica construida desde poesía, papel y tinta.",
  tags: ["Teatro"],
};

const workshopAfterTitleCleanup = {
  id: "agenda_mhnv_fb_colores_primavera",
  title: "Colores de Primavera",
  original_title: "Taller “Colores de Primavera”",
  event_type: "event",
  primary_category: { id: "cursos-talleres-campus", label: "Cursos, talleres y campus" },
  categories: [{ id: "cursos-talleres-campus", label: "Cursos, talleres y campus" }],
  schedule: { mode: "single", start: "2026-09-05T11:00:00-04:00", end: "2026-09-05T11:00:00-04:00", occurrences: [] },
  description: "Actividad práctica familiar.",
  tags: ["Taller"],
};

const mixed = normalizeFormationCycles({
  events: [formationCycle, matriarcasAfterTitleCleanup, workshopAfterTitleCleanup],
});
assert.equal(mixed.events[0].event_type, "program", "formation event still receives lifecycle normalization");
assert.equal(mixed.events[1], matriarcasAfterTitleCleanup, "unrelated theatre event must not be re-normalized by the formation pass");
assert.equal(mixed.events[1].primary_category.id, "teatro", "Matriarcas must remain Teatro after title cleanup");
assert.equal(mixed.events[2], workshopAfterTitleCleanup, "unrelated workshop must not be re-normalized by the formation pass");
assert.equal(mixed.events[2].primary_category.id, "cursos-talleres-campus", "workshop category must remain stable after title cleanup");

console.log("FORMATION_CYCLE_CLASSIFIER_OK");
