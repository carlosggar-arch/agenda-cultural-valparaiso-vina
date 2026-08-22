import assert from "node:assert/strict";
import { dateSpecificHours, nextVenueOpeningForDate, venueHoursForDate } from "./venue-hours.mjs";

const pinole = "Mar–vie 09:30–14:00 y 17:00–19:30 · sáb, dom y festivos 10:00–14:00 y 17:00–19:30 · lunes cerrado.";
assert.equal(dateSpecificHours(pinole, "2026-08-21"), "09:30–14:00 y 17:00–19:30");
assert.equal(dateSpecificHours(pinole, "2026-08-22"), "10:00–14:00 y 17:00–19:30");
assert.equal(dateSpecificHours("Lun–vie 08:00–21:30.", "2026-08-22"), "Cerrado");
assert.equal(dateSpecificHours("Mar–vie 10:00–19:30 · sáb 11:00–19:30.", "2026-08-22"), "11:00–19:30");
assert.equal(dateSpecificHours("Mar–vie 10:00–19:30 · sáb 11:00–19:30.", "2026-08-23"), "Cerrado");

const laboral = {
  location: { venue: "LABoral Centro de Arte y Creación Industrial", city: "Gijón" },
  schedule: { start: "2026-08-01", end: "2026-08-31" },
};
assert.equal(venueHoursForDate(laboral, "gijon", "2026-08-22")?.display, "11:00–19:30");

const nextLaboral = nextVenueOpeningForDate(laboral, "gijon", "2026-08-23");
assert.equal(nextLaboral?.reference_date, "2026-08-25");
assert.equal(nextLaboral?.display, "10:00–19:30");
assert.equal(nextLaboral?.days_ahead, 2);

const closingSunday = {
  ...laboral,
  schedule: { start: "2026-08-23", end: "2026-08-23" },
};
assert.equal(nextVenueOpeningForDate(closingSunday, "gijon", "2026-08-23"), null);

console.log("VENUE_HOURS_DATE_SPECIFIC_OK");
