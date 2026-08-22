import assert from "node:assert/strict";
import {
  classifyClockRoles,
  normalizeEventScheduleContract,
  normalizeScheduleContractDataset,
} from "./schedule-contract.mjs";

const mixed = normalizeEventScheduleContract({
  id: "mixed",
  event_type: "event",
  description: "Horario del museo 10:00–17:30 · función 19:00",
  schedule: { mode: "single", start: "2026-08-21" },
});
assert.deepEqual(mixed.schedule.session_times, ["19:00"]);
assert.equal(mixed.schedule.schedule_display, "19:00");
assert.deepEqual(mixed.schedule.venue_hours, {
  opening_time: "10:00",
  closing_time: "17:30",
  display_text: "10:00–17:30",
});

const two = normalizeEventScheduleContract({
  id: "two",
  event_type: "event",
  description: "Funciones 19:00 y 21:00",
  schedule: { mode: "single", start: "2026-08-21" },
});
assert.deepEqual(two.schedule.session_times, ["19:00", "21:00"]);
assert.equal(two.schedule.schedule_display, "19:00 y 21:00");
assert.equal(two.schedule.event_end_time, null);

const doors = normalizeEventScheduleContract({
  id: "doors",
  event_type: "event",
  description: "Puertas 18:30 · concierto 20:00",
  schedule: { mode: "single", start: "2026-08-21" },
});
assert.equal(doors.schedule.doors_time, "18:30");
assert.deepEqual(doors.schedule.session_times, ["20:00"]);
assert.equal(doors.schedule.schedule_display, "20:00");

const interval = normalizeEventScheduleContract({
  id: "interval",
  event_type: "event",
  description: "Concierto 20:00–22:00",
  schedule: { mode: "single", start: "2026-08-21" },
});
assert.deepEqual(interval.schedule.session_times, ["20:00"]);
assert.equal(interval.schedule.event_end_time, "22:00");
assert.equal(interval.schedule.schedule_display, "20:00–22:00");

const ambiguous = normalizeEventScheduleContract({
  id: "ambiguous",
  event_type: "event",
  description: "10:00 17:30 19:00",
  schedule: { mode: "single", start: "2026-08-21" },
});
assert.deepEqual(ambiguous.schedule.session_times, []);
assert.equal(ambiguous.schedule.schedule_display, null);

const occurrenceAuthority = normalizeEventScheduleContract({
  id: "occurrences",
  event_type: "event",
  session_times: ["10:00"],
  schedule: {
    mode: "multi_session",
    start: "2026-08-21T19:00:00-04:00",
    end: "2026-08-21T22:00:00-04:00",
    session_times: ["11:00"],
    occurrences: [
      { start: "2026-08-21T19:00:00-04:00", end: "2026-08-21T20:00:00-04:00" },
      { start: "2026-08-21T21:00:00-04:00", end: "2026-08-21T22:00:00-04:00" },
    ],
  },
});
assert.deepEqual(occurrenceAuthority.schedule.session_times, ["19:00", "21:00"]);
assert.equal(occurrenceAuthority.schedule.event_end_time, null);
assert.equal(occurrenceAuthority.schedule.schedule_display, "19:00 y 21:00");

const exhibition = normalizeEventScheduleContract({
  id: "exhibition",
  event_type: "event",
  primary_category: { id: "exposiciones", label: "Exposiciones" },
  schedule: {
    mode: "multi_day",
    start: "2026-08-01T10:00:00-04:00",
    end: "2026-08-31T17:30:00-04:00",
    opening_hours: {
      opening_time: "10:00",
      closing_time: "17:30",
      open_weekdays: [1, 2, 3, 4, 5, 6],
      display_text: "Martes a domingo · 10:00–17:30",
    },
  },
});
assert.deepEqual(exhibition.schedule.session_times, []);
assert.equal(exhibition.schedule.venue_hours.opening_time, "10:00");
assert.equal(exhibition.schedule.venue_hours.closing_time, "17:30");

const first = normalizeScheduleContractDataset({ events: [mixed, two, doors, interval, ambiguous, occurrenceAuthority, exhibition] });
const second = normalizeScheduleContractDataset(first);
assert.deepEqual(second, first);

const parsed = classifyClockRoles("Horario del museo 10:00–17:30 · función 19:00");
assert.deepEqual(parsed.raw_times, ["10:00", "17:30", "19:00"]);
assert.deepEqual(parsed.session_times, ["19:00"]);

console.log("SCHEDULE_CONTRACT_POINT8_OK");
