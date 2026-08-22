import assert from "node:assert/strict";

import { formatSchedule } from "../../assets/event-schedule-display.mjs";
import { normalizeEventScheduleContract } from "../schedule-contract.mjs";
import { hasEventSpecificTime, withMissingEventTimeFallback } from "../today-session-presentation.mjs";
import { dailyExhibitionHours, nextDailyExhibitionOpening } from "../date-aware-exhibition-hours.mjs";

const settings = {
  locale: "es-CL",
  timezone: "America/Santiago",
  referenceDate: "2026-08-21",
  now: new Date("2026-08-21T12:00:00-04:00"),
};

function normalized(event) {
  return normalizeEventScheduleContract(event);
}

function formatted(event, options = settings) {
  return formatSchedule(normalized(event).schedule, options);
}

const museumAndFunction = normalized({
  event_type: "event",
  description: "Horario del museo 10:00–17:30 · función 19:00",
  schedule: { mode: "single", start: "2026-08-21" },
});
assert.deepEqual(museumAndFunction.schedule.session_times, ["19:00"]);
assert.equal(museumAndFunction.schedule.schedule_display, "19:00");
assert.match(formatSchedule(museumAndFunction.schedule, settings), /19:00$/);
assert.doesNotMatch(formatSchedule(museumAndFunction.schedule, settings), /10:00|17:30/);

const twoFunctions = {
  event_type: "event",
  description: "Funciones 19:00 y 21:00",
  schedule: { mode: "single", start: "2026-08-21" },
};
assert.match(formatted(twoFunctions), /19:00 y 21:00$/);

const doors = normalized({
  event_type: "event",
  description: "Puertas 18:30 · concierto 20:00",
  schedule: { mode: "single", start: "2026-08-21" },
});
assert.equal(doors.schedule.doors_time, "18:30");
assert.match(formatSchedule(doors.schedule, settings), /20:00$/);
assert.doesNotMatch(formatSchedule(doors.schedule, settings), /18:30/);

const interval = {
  event_type: "event",
  description: "Concierto 20:00–22:00",
  schedule: { mode: "single", start: "2026-08-21" },
};
assert.match(formatted(interval), /20:00–22:00$/);

const ambiguous = normalized({
  event_type: "event",
  description: "10:00 17:30 19:00",
  schedule: { mode: "single", start: "2026-08-21", display_text: "10:00 17:30 19:00" },
});
assert.deepEqual(ambiguous.schedule.session_times, []);
assert.equal(ambiguous.schedule.schedule_display, null);
assert.doesNotMatch(formatSchedule(ambiguous.schedule, settings), /10:00|17:30|19:00/);
assert.equal(hasEventSpecificTime(ambiguous.schedule), false);

const occurrences = normalized({
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
assert.match(formatSchedule(occurrences.schedule, settings), /19:00 y 21:00$/);
assert.match(formatSchedule(occurrences.schedule, { ...settings, referenceDate: "2026-08-22" }), /20:00$/);
assert.doesNotMatch(
  formatSchedule(occurrences.schedule, { ...settings, referenceDate: "2026-08-23" }),
  /19:00 y 21:00|20:00$/,
);

const exhibition = normalized({
  event_type: "event",
  primary_category: { id: "exposiciones" },
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
assert.match(formatSchedule(exhibition.schedule, settings), /10:00–17:30/);
assert.match(formatSchedule(exhibition.schedule, { ...settings, referenceDate: "2026-08-24" }), /Cerrado/);
const monday = dailyExhibitionHours(exhibition.schedule, { ...settings, referenceDate: "2026-08-24" });
assert.equal(monday?.closed, true);
const next = nextDailyExhibitionOpening(exhibition.schedule, { ...settings, referenceDate: "2026-08-24", maxDays: 7 });
assert.equal(next?.referenceDateKey, "2026-08-25");
assert.equal(next?.label, "10:00–17:30");

const venueOnly = normalized({
  event_type: "event",
  description: "Horario del museo 10:00–17:30",
  schedule: { mode: "multi_day", start: "2026-08-21", end: "2026-08-30" },
});
assert.equal(hasEventSpecificTime(venueOnly.schedule), false);
const venueOnlyEventSchedule = { ...venueOnly.schedule };
delete venueOnlyEventSchedule.venue_hours;
assert.match(
  withMissingEventTimeFallback(formatSchedule(venueOnlyEventSchedule, settings), venueOnlyEventSchedule),
  /Consultar horario en la fuente$/,
);

console.log("SCHEDULE_CONTRACT_POINT8_DISPLAY_OK");
