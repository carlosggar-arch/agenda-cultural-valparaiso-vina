import assert from "node:assert/strict";
import {
  dailyExhibitionHours,
  exhibitionReferenceDateKey,
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

const future = {
  ...palacioRioja,
  start: "2026-08-25T10:00:00-04:00",
  end: "2026-09-10T17:30:00-04:00",
};
assert.equal(exhibitionReferenceDateKey(future, {
  timezone: "America/Santiago",
  now: new Date("2026-08-21T12:00:00-04:00"),
}), "2026-08-25");

const unsafeFreeText = {
  start: "2026-08-21",
  end: "2026-09-30",
  opening_hours: {
    display_text: "Mar–vie 09:30–14:00 y 17:00–19:30 · sáb y dom 10:00–14:00",
  },
};
assert.equal(dailyExhibitionHours(unsafeFreeText, {
  timezone: "Europe/Madrid",
  now: new Date("2026-08-21T12:00:00+02:00"),
}), null);

console.log("DATE_AWARE_EXHIBITION_HOURS_OK");
