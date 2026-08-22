import assert from "node:assert/strict";
import {
  dailyExhibitionHours,
  exhibitionReferenceDateKey,
  hoursForDateFromDisplay,
  nextDailyExhibitionOpening,
} from "./date-aware-exhibition-hours.mjs";

const palacioRioja = {
  start: "2026-08-21T06:00:00-04:00",
  end: "2026-08-30T17:30:00-04:00",
  opening_time: "10:00",
  closing_time: "17:30",
  opening_hours: {
    mode: "weekly",
    open_weekdays: [1, 2, 3, 4, 5, 6],
    opening_time: "10:00",
    closing_time: "17:30",
    display_text: "Martes a domingo · 10:00–17:30",
    reference_date: "2026-08-30",
    is_open_on_reference_date: true,
  },
};

const friday = dailyExhibitionHours(palacioRioja, {
  timezone: "America/Santiago",
  now: new Date("2026-08-21T12:00:00-04:00"),
});
assert.equal(friday.referenceDateKey, "2026-08-21");
assert.equal(friday.label, "10:00–17:30");
assert.equal(friday.closed, false);
assert.doesNotMatch(friday.label, /martes|domingo/i);

const monday = dailyExhibitionHours(palacioRioja, {
  timezone: "America/Santiago",
  referenceDate: "2026-08-24",
});
assert.equal(monday.referenceDateKey, "2026-08-24");
assert.equal(monday.label, "Cerrado");
assert.equal(monday.closed, true);

const nextAfterMonday = nextDailyExhibitionOpening(palacioRioja, {
  timezone: "America/Santiago",
  referenceDate: "2026-08-24",
});
assert.equal(nextAfterMonday.referenceDateKey, "2026-08-25");
assert.equal(nextAfterMonday.label, "10:00–17:30");
assert.equal(nextAfterMonday.closed, false);
assert.equal(nextAfterMonday.daysAhead, 1);

const endsClosed = {
  ...palacioRioja,
  start: "2026-08-24",
  end: "2026-08-24",
};
assert.equal(nextDailyExhibitionOpening(endsClosed, {
  timezone: "America/Santiago",
  referenceDate: "2026-08-24",
}), null);

const future = {
  ...palacioRioja,
  start: "2026-08-25T10:00:00-04:00",
  end: "2026-09-10T17:30:00-04:00",
};
assert.equal(exhibitionReferenceDateKey(future, {
  timezone: "America/Santiago",
  now: new Date("2026-08-21T12:00:00-04:00"),
}), "2026-08-25");

// Free-form official schedules are safe once resolved against the exact viewed
// date. This covers the Gijón venue registry without moving city knowledge into
// the renderer.
const splitWeekly = {
  start: "2026-08-01",
  end: "2026-09-30",
  opening_hours: {
    display_text: "Mar–vie 09:30–14:00 y 17:00–19:30 · sáb y dom 10:00–14:00",
  },
};
const splitFriday = dailyExhibitionHours(splitWeekly, {
  timezone: "Europe/Madrid",
  referenceDate: "2026-08-21",
});
assert.equal(splitFriday.label, "09:30–14:00 y 17:00–19:30");
assert.equal(splitFriday.closed, false);
assert.equal(splitFriday.source, "venue_hours_date_resolved");

const splitSaturday = dailyExhibitionHours(splitWeekly, {
  timezone: "Europe/Madrid",
  referenceDate: "2026-08-22",
});
assert.equal(splitSaturday.label, "10:00–14:00");
assert.equal(splitSaturday.closed, false);

const splitMonday = dailyExhibitionHours(splitWeekly, {
  timezone: "Europe/Madrid",
  referenceDate: "2026-08-24",
});
assert.equal(splitMonday.label, "Cerrado");
assert.equal(splitMonday.closed, true);

assert.equal(hoursForDateFromDisplay("Lun–vie 08:00–21:30.", "2026-08-22"), "Cerrado");
assert.equal(hoursForDateFromDisplay("Lun–sáb 08:00–21:30.", "2026-08-22"), "08:00–21:30");

const botanical = "Ene, feb, oct–dic · 10:00–18:00 · marzo 10:00–19:00 · abril y septiembre 10:00–20:00 · mayo–agosto 10:00–21:00. Habitualmente mar–dom; lunes también abre en julio y agosto.";
assert.equal(hoursForDateFromDisplay(botanical, "2026-08-22"), "10:00–21:00");
assert.equal(hoursForDateFromDisplay(botanical, "2026-08-24"), "10:00–21:00", "August Monday exception remains open");
assert.equal(hoursForDateFromDisplay(botanical, "2026-11-22"), "10:00–18:00");

console.log("DATE_AWARE_EXHIBITION_HOURS_OK");
