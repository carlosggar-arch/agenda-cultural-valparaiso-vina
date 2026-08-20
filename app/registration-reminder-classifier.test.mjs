import assert from "node:assert/strict";
import {
  isRegistrationReminder,
  normalizeFormationCycles,
} from "./formation-cycle-classifier.js";

function formationEvent(overrides = {}) {
  return {
    id: "fixture-registration",
    title: "Campus de Verano 2026",
    event_type: "event",
    primary_category: { id: "formacion-taller", label: "Formación / taller" },
    categories: [{ id: "formacion-taller", label: "Formación / taller" }],
    schedule: {
      mode: "multi_day",
      start: "2026-06-30T09:00:00+02:00",
      end: "2026-08-28T17:00:00+02:00",
      occurrences: [],
    },
    public_status: { sold_out: false },
    links: {},
    tags: [],
    ...overrides,
  };
}

const campus = formationEvent({
  public_status: {
    sold_out: true,
    advisory_text: "Plazas agotadas según la fuente oficial.",
  },
});
assert.equal(isRegistrationReminder(campus), true, "a long formation enrollment/booking offer must be a reminder, not a dated event");

const normalizedCampus = normalizeFormationCycles({ events: [campus] }).events[0];
assert.equal(normalizedCampus.event_type, "registration_period");
assert.equal(normalizedCampus.editorial.classification, "registration_period");
assert.equal(normalizedCampus.editorial.original_event_type, "event");
assert.equal(normalizedCampus.schedule.start, campus.schedule.start, "source activity window must remain available as source metadata");

const explicitEnrollment = formationEvent({
  title: "Escuela creativa de verano",
  description: "Periodo de inscripción abierto hasta completar plazas.",
  public_status: {},
});
assert.equal(isRegistrationReminder(explicitEnrollment), true, "explicit enrollment periods must be separated structurally");

const registrationProgram = formationEvent({
  id: "fixture-registration-program",
  title: "Programa municipal: inscripciones",
  event_type: "program",
  primary_category: { id: "cultura", label: "Cultura" },
  categories: [{ id: "cultura", label: "Cultura" }],
  description: "Plazos de inscripción para las actividades de verano.",
  public_status: {},
});
assert.equal(isRegistrationReminder(registrationProgram), true, "administrative programmes whose content is the registration process must enter the reminder section");
const normalizedProgram = normalizeFormationCycles({ events: [registrationProgram] }).events[0];
assert.equal(normalizedProgram.event_type, "registration_period");
assert.equal(normalizedProgram.editorial.original_event_type, "program");

const culturalProgram = formationEvent({
  id: "fixture-cultural-program",
  title: "Festival municipal de verano",
  event_type: "program",
  primary_category: { id: "cultura", label: "Cultura" },
  categories: [{ id: "cultura", label: "Cultura" }],
  description: "Programación cultural de julio y agosto.",
  public_status: {},
});
assert.equal(isRegistrationReminder(culturalProgram), false, "ordinary cultural programmes must remain programmes");

const singleWorkshop = formationEvent({
  title: "Taller de grabado",
  description: "Requiere inscripción previa.",
  schedule: {
    mode: "single",
    start: "2026-08-23T11:00:00+02:00",
    end: "2026-08-23T13:00:00+02:00",
    occurrences: [],
  },
  links: { registration: "https://example.org/register" },
});
assert.equal(isRegistrationReminder(singleWorkshop), false, "a real one-day workshop must stay an event even if registration is required");

const recurringCourse = formationEvent({
  title: "Curso semanal de fotografía",
  description: "Inscripción previa.",
  schedule: {
    mode: "multi_day",
    start: "2026-08-01T18:00:00+02:00",
    end: "2026-09-15T20:00:00+02:00",
    occurrences: [
      { start: "2026-08-25T18:00:00+02:00", end: "2026-08-25T20:00:00+02:00" },
      { start: "2026-09-01T18:00:00+02:00", end: "2026-09-01T20:00:00+02:00" },
    ],
  },
});
assert.equal(isRegistrationReminder(recurringCourse), false, "explicit session occurrences are real scheduled activities, not registration reminders");

const soldOutExhibition = formationEvent({
  title: "Exposición temporal",
  primary_category: { id: "exposiciones", label: "Exposiciones" },
  categories: [{ id: "exposiciones", label: "Exposiciones" }],
  public_status: { sold_out: true, advisory_text: "Entradas agotadas" },
});
assert.equal(isRegistrationReminder(soldOutExhibition), false, "sold-out status alone must never reclassify unrelated cultural events");

console.log("REGISTRATION_REMINDER_CLASSIFIER_OK");
