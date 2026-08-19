import assert from "node:assert/strict";
import test from "node:test";

import { eventIsCurrentOrFuture, removeExpiredDatedEvents } from "./runtime-past-event-guard.mjs";

const now = new Date("2026-08-19T18:30:00-04:00");

function event(id, start, end = start, event_type = "event") {
  return { id, event_type, schedule: { start, end, occurrences: [] } };
}

test("hides single-day events from yesterday", () => {
  assert.equal(eventIsCurrentOrFuture(event("past", "2026-08-18T20:00:00-04:00"), {
    now,
    timeZone: "America/Santiago",
  }), false);
});

test("keeps ongoing multi-day events that started yesterday", () => {
  assert.equal(eventIsCurrentOrFuture(event("ongoing", "2026-08-18T10:00:00-04:00", "2026-08-21"), {
    now,
    timeZone: "America/Santiago",
  }), true);
});

test("keeps programs and flexible offers outside the dated-event guard", () => {
  assert.equal(eventIsCurrentOrFuture(event("program", "2026-08-01", "2026-08-31", "program"), {
    now,
    timeZone: "America/Santiago",
  }), true);
});

test("filters only expired dated events from the runtime dataset", () => {
  const dataset = {
    timezone: "America/Santiago",
    events: [
      event("past", "2026-08-18T20:00:00-04:00"),
      event("today", "2026-08-19T20:00:00-04:00"),
      event("ongoing", "2026-08-18", "2026-08-21"),
    ],
  };
  const result = removeExpiredDatedEvents(dataset, { now, timeZone: "America/Santiago" });
  assert.deepEqual(result.events.map((item) => item.id), ["today", "ongoing"]);
});
