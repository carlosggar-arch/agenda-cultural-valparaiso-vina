import assert from "node:assert/strict";
import { compactScheduleDayLabel, formatSchedule } from "../assets/event-schedule-display.mjs";
import { eventMatchesCanonicalSection } from "./public-selection-core.mjs";
import {
  hasEventSpecificTime,
  todaySessionScheduleLabel,
  withMissingEventTimeFallback,
} from "./today-session-presentation.mjs";

const valpo = {
  locale: "es-CL",
  timezone: "America/Santiago",
  now: new Date("2026-08-20T15:14:00-04:00"),
};

const odisea = {
  title: "La odisea",
  schedule: {
    mode: "multi_day",
    start: "2026-08-20T17:10:00-04:00",
    end: "2026-08-20T20:10:00-04:00",
    display_text: "20-08-2026 · 17:10–20:10",
    occurrences: [],
  },
  description: "Dirección: Condell 1585, Valparaíso. Funciones: Jueves 20 de agosto, 17:10 hrs; Viernes 21 de agosto, 17:30 hrs; Domingo 23 de agosto, 15:00 hrs",
};

const todayOdisea = todaySessionScheduleLabel(odisea, valpo);
assert.match(todayOdisea, /20 ago/i);
assert.match(todayOdisea, /17:10/);
assert.doesNotMatch(todayOdisea, /17:30/);
assert.doesNotMatch(todayOdisea, /15:00/);

const fridayOdisea = todaySessionScheduleLabel(odisea, {
  ...valpo,
  now: new Date("2026-08-21T12:00:00-04:00"),
});
assert.match(fridayOdisea, /21 ago/i);
assert.match(fridayOdisea, /17:30/);
assert.doesNotMatch(fridayOdisea, /17:10/);
assert.doesNotMatch(fridayOdisea, /15:00/);

const structured = {
  schedule: {
    mode: "multi_session",
    occurrences: [
      { start: "2026-08-20T11:00:00-04:00", end: null },
      { start: "2026-08-20T19:00:00-04:00", end: null },
      { start: "2026-08-21T17:30:00-04:00", end: null },
    ],
  },
};
const structuredToday = todaySessionScheduleLabel(structured, valpo);
assert.match(structuredToday, /11:00/);
assert.match(structuredToday, /19:00/);
assert.doesNotMatch(structuredToday, /17:30/);

const ordinaryTimedEvent = {
  schedule: {
    mode: "single",
    start: "2026-08-20T18:00:00-04:00",
    end: "2026-08-20T20:00:00-04:00",
    occurrences: [{ start: "2026-08-20T18:00:00-04:00", end: "2026-08-20T20:00:00-04:00" }],
  },
  description: "Una única función esta tarde.",
};
assert.equal(todaySessionScheduleLabel(ordinaryTimedEvent, valpo), null);
assert.equal(hasEventSpecificTime(ordinaryTimedEvent.schedule), true);
assert.equal(withMissingEventTimeFallback("jue, 20 ago · 18:00", ordinaryTimedEvent.schedule), "jue, 20 ago · 18:00");

const noSessionToday = {
  schedule: {
    mode: "multi_session",
    occurrences: [
      { start: "2026-08-21T17:30:00-04:00", end: null },
      { start: "2026-08-23T15:00:00-04:00", end: null },
    ],
  },
};
assert.equal(todaySessionScheduleLabel(noSessionToday, valpo), null);

const noTimeRun = {
  mode: "multi_day",
  start: "2026-08-21",
  end: "2026-08-30",
  display_text: "21–30 ago",
  occurrences: [],
};
assert.equal(hasEventSpecificTime(noTimeRun), false);
assert.equal(
  withMissingEventTimeFallback("21–30 ago", noTimeRun),
  "21–30 ago · Consultar horario en la fuente",
);
assert.equal(
  withMissingEventTimeFallback("", noTimeRun),
  "Consultar horario en la fuente",
);

const timeOnlyInDisplay = {
  start: "2026-08-21",
  end: "2026-08-30",
  display_text: "Funciones · 22:00",
};
assert.equal(hasEventSpecificTime(timeOnlyInDisplay), true);
assert.equal(withMissingEventTimeFallback("21–30 ago · 22:00", timeOnlyInDisplay), "21–30 ago · 22:00");

const conflictingSecretoMontana = {
  description: "Funciones: martes 15 de septiembre de 2026, 20:00 hrs; martes 15 de septiembre de 2026, 20:30 hrs.",
  schedule: {
    mode: "dated",
    start: "2026-09-15",
    end: "2026-09-15",
    display_text: "Horario por confirmar",
    occurrences: [],
    start_confidence: "explicit_date_conflicting_time",
    end_confidence: "explicit_date_conflicting_time",
  },
};
const secretoOptions = { ...valpo, now: new Date("2026-09-15T12:00:00-03:00") };
assert.equal(todaySessionScheduleLabel(conflictingSecretoMontana, secretoOptions), null);
assert.equal(
  withMissingEventTimeFallback("mar, 15 sept", conflictingSecretoMontana.schedule),
  "mar, 15 sept · Horario por confirmar",
);

console.log("TODAY_SESSION_PRESENTATION_OK");

for (const [city, offset] of [
  [{ id: "valparaiso", timezone: "America/Santiago", locale: "es-CL" }, "-03:00"],
  [{ id: "gijon", timezone: "Europe/Madrid", locale: "es-ES" }, "+02:00"],
]) {
  const workshop = {
    title: "Escuelita de creación", event_type: "workshop",
    schedule: {
      mode: "multi_session", start: "2026-09-20", end: "2026-09-27",
      occurrences: [
        { start: `2026-09-20T10:00:00${offset}`, end: `2026-09-20T12:30:00${offset}` },
        { start: `2026-09-27T11:00:00${offset}`, end: `2026-09-27T13:00:00${offset}` },
      ],
      display_text: "Horarios: 27 de septiembre de 2026 16:00",
    },
    description: "Horarios: 27 de septiembre de 2026 16:00",
  };
  const now = new Date(`2026-09-27T09:00:00${offset}`);
  const options = { ...city, now, referenceDate: "2026-09-27" };
  const label = todaySessionScheduleLabel(workshop, options);
  assert.match(label, /11:00–13:00/);
  assert.doesNotMatch(label, /10:00|12:30|16:00/, "only the current canonical session survives");
  assert.match(formatSchedule(workshop.schedule, options), /11:00–13:00/);
  assert.equal(eventMatchesCanonicalSection(workshop, "hoy", city, now), true);
  const gap = new Date(`2026-09-21T09:00:00${offset}`);
  assert.equal(eventMatchesCanonicalSection(workshop, "hoy", city, gap), false);
  assert.equal(eventMatchesCanonicalSection(workshop, "proximos", city, gap), true);
  assert.equal(compactScheduleDayLabel(workshop.schedule, { ...city, now: gap }).today, false);
  assert.match(formatSchedule(workshop.schedule, { ...city, now: gap, referenceDate: "2026-09-21" }), /27.*11:00–13:00/);
  const exhibition = { ...workshop, event_type: "exhibition",
    schedule: { start: "2026-09-20", end: "2026-09-27", occurrences: [] } };
  assert.equal(eventMatchesCanonicalSection(exhibition, "hoy", city, gap), true, "continuous exhibitions remain available");
  const dateOnly = { ...workshop, schedule: { ...workshop.schedule,
    occurrences: [{ start: "2026-09-20" }, { start: "2026-09-27" }] } };
  assert.equal(todaySessionScheduleLabel(dateOnly, options), null, "legacy prose must not restore unverified hours");
  const pendingToday = { ...workshop.schedule,
    occurrences: [{ start: "2026-09-27" }, { start: `2026-10-04T18:00:00${offset}` }],
  };
  const pendingLabel = formatSchedule(pendingToday, options);
  assert.match(pendingLabel, /27.*Horario por confirmar/);
  assert.doesNotMatch(pendingLabel, /18:00|oct/, "a date-only session today must not be replaced by a later timed session");
  const completed = { ...workshop.schedule,
    occurrences: [{ start: `2026-08-22T12:00:00${offset}`, end: `2026-08-22T13:30:00${offset}` }, { start: "2026-10-10" }],
    display_text: "22 de agosto de 2026 12:00–13:30; 10 de octubre horario por confirmar",
  };
  const afterLast = { ...city, now: new Date(`2026-10-11T09:00:00${offset}`) };
  const completedLabel = formatSchedule(completed, afterLast);
  assert.match(completedLabel, /10 oct.*Horario por confirmar/);
  assert.doesNotMatch(completedLabel, /ago|12:00|13:30/, "an expired dated entry never revives an older session from prose");
  assert.equal(compactScheduleDayLabel(completed, afterLast).text, "10 oct");
}
console.log("DAILY_OCCURRENCE_DISPLAY_AND_CITY_PARITY_OK");
