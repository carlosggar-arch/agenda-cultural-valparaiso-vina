import assert from "node:assert/strict";
import { compactScheduleDayLabel, formatSchedule } from "../../assets/event-schedule-display.mjs";

const valpo = {
  locale: "es-CL",
  timezone: "America/Santiago",
  now: new Date("2026-08-16T18:00:00-04:00"),
};

const rioja = {
  mode: "multi_day",
  start: "2026-08-15T10:00:00-04:00",
  end: "2026-08-30",
  opening_time: "10:00",
  closing_time: "17:30",
  hours_confidence: "source_schedule_pair",
};
assert.match(formatSchedule(rioja, valpo), /10:00–17:30/);
assert.equal(compactScheduleDayLabel(rioja, valpo)?.text, "Hoy");

const baburizza = {
  mode: "multi_day",
  start: "2026-08-15",
  end: "2026-08-30",
  opening_time: "10:00",
  closing_time: "18:00",
  hours_confidence: "official_venue_schedule",
  opening_hours: {
    opening_time: "10:00",
    closing_time: "18:00",
    display_text: "Martes a domingo · 10:00–18:00",
    is_open_on_reference_date: true,
  },
};
assert.match(formatSchedule(baburizza, valpo), /10:00–18:00/);

const closedMuseum = {
  ...baburizza,
  opening_time: null,
  closing_time: null,
  opening_hours: {
    ...baburizza.opening_hours,
    is_open_on_reference_date: false,
  },
};
assert.match(formatSchedule(closedMuseum, valpo), /Cerrado hoy/);
assert.match(formatSchedule(closedMuseum, valpo), /Martes a domingo/);

const cinema = {
  mode: "single",
  start: "2026-08-16T15:00:00-04:00",
  end: "2026-08-16T17:05:00-04:00",
};
const cinemaLabel = formatSchedule(cinema, valpo);
assert.match(cinemaLabel, /15:00–17:05/);

const noTime = {
  mode: "multi_day",
  start: "2026-08-20",
  end: "2026-08-22",
};
assert.doesNotMatch(formatSchedule(noTime, valpo), /00:00/);

console.log("Shared schedule formatter runtime tests: OK");
