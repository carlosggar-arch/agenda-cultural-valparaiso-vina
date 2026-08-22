import assert from "node:assert/strict";

import { formatSchedule } from "../../assets/event-schedule-display.mjs";
import { normalizeEventScheduleContract } from "../schedule-contract.mjs";

const settings = {
  locale: "es-CL",
  timezone: "America/Santiago",
  referenceDate: "2026-08-21",
  now: new Date("2026-08-21T12:00:00-04:00"),
};

function formatted(event) {
  return formatSchedule(normalizeEventScheduleContract(event).schedule, settings);
}

const museumAndFunction = {
  event_type: "event",
  description: "Horario del museo 10:00–17:30 · función 19:00",
  schedule: { mode: "single", start: "2026-08-21" },
};
assert.match(formatted(museumAndFunction), /19:00$/);
assert.doesNotMatch(formatted(museumAndFunction), /10:00|17:30/);

const twoFunctions = {
  event_type: "event",
  description: "Funciones 19:00 y 21:00",
  schedule: { mode: "single", start: "2026-08-21" },
};
assert.match(formatted(twoFunctions), /19:00 y 21:00$/);

const doors = {
  event_type: "event",
  description: "Puertas 18:30 · concierto 20:00",
  schedule: { mode: "single", start: "2026-08-21" },
};
assert.match(formatted(doors), /20:00$/);
assert.doesNotMatch(formatted(doors), /18:30/);

const interval = {
  event_type: "event",
  description: "Concierto 20:00–22:00",
  schedule: { mode: "single", start: "2026-08-21" },
};
assert.match(formatted(interval), /20:00–22:00$/);

const ambiguous = {
  event_type: "event",
  description: "10:00 17:30 19:00",
  schedule: { mode: "single", start: "2026-08-21", display_text: "10:00 17:30 19:00" },
};
const ambiguousLabel = formatted(ambiguous);
assert.doesNotMatch(ambiguousLabel, /10:00|17:30|19:00/);

const occurrences = normalizeEventScheduleContract({
  event_type: "event",
  schedule: {
    mode: "multi_session",
    start: "2026-08-21T19:00:00-04:00",
    end: "2026-08-22T22:00:00-04:00",
    occurrences: [
      { start: "2026-08-21T19:00:00-04:00", end: "2026-08-21T20:00:00-04:00" },
      { start: "2026-08-21T21:00:00-04:00", end: "2026-08-21T22:00:00-04:00" },
      { start: "2026-08-22T20:00:00-04:00", end: "2026-08-22T22:00:00-04:00" },
    ],
  },
});
const today = formatSchedule(occurrences.schedule, settings);
assert.match(today, /19:00 y 21:00$/);
assert.doesNotMatch(today, /20:00$/);

const tomorrow = formatSchedule(occurrences.schedule, { ...settings, referenceDate: "2026-08-22" });
assert.match(tomorrow, /20:00$/);
assert.doesNotMatch(tomorrow, /19:00 y 21:00/);

const outside = formatSchedule(occurrences.schedule, { ...settings, referenceDate: "2026-08-23" });
assert.doesNotMatch(outside, /19:00 y 21:00|20:00$/);

const exhibition = normalizeEventScheduleContract({
  event_type: "event",
  primary_category: { id: "exposiciones", label: "Exposiciones" },
  schedule: {
    mode: "multi_day",
    start: "2026-08-01",
    end: "2026-08-31",
    venue_hours: {
      opening_time: "10:00",
      closing_time: "17:30",
      open_weekdays: [1, 2, 3, 4, 5, 6],
      display_text: "Martes a domingo · 10:00–17:30",
    },
  },
});
const fridayHours = formatSchedule(exhibition.schedule, settings);
assert.match(fridayHours, /10:00–17:30/);
const mondayHours = formatSchedule(exhibition.schedule, { ...settings, referenceDate: "2026-08-24" });
assert.match(mondayHours, /Cerrado/);

console.log("SCHEDULE_CONTRACT_POINT8_DISPLAY_OK");
