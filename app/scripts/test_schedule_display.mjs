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

const nestedWeeklyHours = {
  mode: "multi_day",
  start: "2026-08-14",
  end: "2026-10-04",
  display_text: "2026-08-14 – 2026-10-04",
  opening_hours: {
    opening_time: "10:00",
    closing_time: "18:00",
    display_text: "Martes a domingo · 10:00–18:00",
    is_open_on_reference_date: true,
  },
};
assert.match(formatSchedule(nestedWeeklyHours, valpo), /Martes a domingo/);
assert.match(formatSchedule(nestedWeeklyHours, valpo), /10:00–18:00/);

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

const sourceDisplayHours = {
  mode: "multi_day",
  start: "2026-08-17",
  end: "2026-08-23",
  display_text: "2026-08-17 · 11:30, 13:00, 18:30",
  occurrences: [],
};
assert.equal(formatSchedule(sourceDisplayHours, valpo), "2026-08-17 · 11:30, 13:00, 18:30");

const galleryFlattenedHours = {
  mode: "multi_day",
  start: "2026-08-18T10:00:00-04:00",
  end: "2026-08-21",
  display_text: "2026-08-18 · 10:00, 18:00, 11:00, 17:00",
  occurrences: [],
};
const galleryLabel = formatSchedule(galleryFlattenedHours, valpo);
assert.match(galleryLabel, /10:00–18:00/);
assert.match(galleryLabel, /11:00–17:00/);
assert.doesNotMatch(galleryLabel, /10:00,\s*18:00,\s*11:00,\s*17:00/);

const artequinFlattenedHours = {
  mode: "multi_day",
  start: "2026-08-19T18:30:00-04:00",
  end: "2026-08-22",
  display_text: "2026-08-19 · 18:30, 20:00, 10:00, 14:00",
  occurrences: [],
};
const artequinLabel = formatSchedule(artequinFlattenedHours, valpo);
assert.match(artequinLabel, /18:30–20:00/);
assert.match(artequinLabel, /10:00–14:00/);
assert.doesNotMatch(artequinLabel, /18:30,\s*20:00,\s*10:00,\s*14:00/);

const repeatedFunctions = {
  mode: "single",
  start: "2026-08-18",
  end: "2026-08-18",
  occurrences: [
    { start: "2026-08-18T11:00:00-04:00" },
    { start: "2026-08-18T15:30:00-04:00" },
    { start: "2026-08-18T19:00:00-04:00" },
  ],
};
const repeatedLabel = formatSchedule(repeatedFunctions, valpo);
assert.match(repeatedLabel, /11:00/);
assert.match(repeatedLabel, /15:30/);
assert.match(repeatedLabel, /19:00/);

const malformedSameDayEnd = {
  mode: "dated",
  start: "2026-08-18T20:00:00-04:00",
  end: "2026-08-18",
  display_text: "18-08-2026 20:00 – 2026-08-18",
};
const normalizedSameDayLabel = formatSchedule(malformedSameDayEnd, valpo);
assert.match(normalizedSameDayLabel, /20:00/);
assert.doesNotMatch(normalizedSameDayLabel, /–\s*2026-08-18/);
assert.doesNotMatch(normalizedSameDayLabel, /20:00\s*–/);

const noTime = {
  mode: "multi_day",
  start: "2026-08-20",
  end: "2026-08-22",
};
assert.doesNotMatch(formatSchedule(noTime, valpo), /00:00/);

console.log("Shared schedule formatter runtime tests: OK");
