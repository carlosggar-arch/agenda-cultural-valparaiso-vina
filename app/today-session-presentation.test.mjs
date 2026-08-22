import assert from "node:assert/strict";
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

console.log("TODAY_SESSION_PRESENTATION_OK");
