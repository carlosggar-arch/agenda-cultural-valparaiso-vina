import test from "node:test";
import assert from "node:assert/strict";

import {
  calendarOccurrences,
  scheduleLabel,
} from "../assets/agenda-core-base.mjs";
import { formatSchedule } from "../assets/event-schedule-display.mjs";
import { canonicalEventIds } from "../app/public-selection-core.mjs";
import { sessionScheduleLabelForDate } from "../app/today-session-presentation.mjs";

const city = Object.freeze({ locale: "es-CL", timezone: "America/Santiago" });
const now = new Date("2026-09-15T12:00:00-03:00");
const event = Object.freeze({
  id: "agenda_0a2a93574ec11b23a05dc552",
  title: "Secreto en la Montaña (2005)",
  event_type: "event",
  primary_category: { id: "cine", label: "Cine" },
  categories: [{ id: "cine", label: "Cine" }],
  description: (
    "Secreto en la Montaña (2005). Funciones: martes 15 de septiembre de 2026, 20:00 hrs; "
    + "martes 15 de septiembre de 2026, 20:30 hrs."
  ),
  schedule: {
    mode: "dated",
    start: "2026-09-15",
    end: "2026-09-15",
    timezone: "America/Santiago",
    display_text: "Horario por confirmar",
    occurrences: [],
    start_confidence: "explicit_date_conflicting_time",
    end_confidence: "explicit_date_conflicting_time",
  },
});

test("keeps the accredited date exactly once in the 15 September filter", () => {
  assert.deepEqual(canonicalEventIds([event], "hoy", city, now), [event.id]);
});

test("WEB and APP expose the date with a pending time and no inferred sessions", () => {
  const options = { ...city, now, referenceDate: "2026-09-15" };
  const web = scheduleLabel(event.schedule);
  const app = formatSchedule(event.schedule, options);
  assert.match(web, /15 de septiembre de 2026 · Horario por confirmar/);
  assert.match(app, /15 sept.*Horario por confirmar/i);
  assert.equal(sessionScheduleLabelForDate(event, options), null);
  for (const value of [web, app]) {
    assert.doesNotMatch(value, /00:00|20:00|20:30|todo el d[ií]a/i);
  }
});

test("does not create an all-day calendar occurrence while the time conflicts", () => {
  assert.deepEqual(calendarOccurrences(event), []);
});
