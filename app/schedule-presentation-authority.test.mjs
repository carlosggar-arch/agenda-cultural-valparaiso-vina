import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const schedule = read("./schedule-display.js");
const legacy = read("./exhibition-hours.js");

for (const marker of [
  "dailyExhibitionHours",
  "nextDailyExhibitionOpening",
  "venueHoursForDate",
  "nextVenueOpeningForDate",
  "exhibitionVisitHoursForDisplay",
  "Horario de hoy:",
  "Próxima apertura:",
  "Horario de visita:",
  "Horario del recinto:",
]) {
  assert.match(schedule, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")), `schedule-display must own ${marker}`);
}

for (const forbidden of [
  "dailyExhibitionHours",
  "nextDailyExhibitionOpening",
  "venueHoursForDate",
  "nextVenueOpeningForDate",
  ".textContent =",
  "replaceChildren(",
  "insertAdjacentElement(",
  ".hidden =",
]) {
  assert.equal(legacy.includes(forbidden), false, `retired exhibition-hours shim must not own ${forbidden}`);
}

assert.match(legacy, /compatibility shim/i, "retired module must document its cache-compatibility purpose");
console.log("SINGLE_SCHEDULE_PRESENTATION_AUTHORITY_OK");
