import assert from "node:assert/strict";
import test from "node:test";

import { eventIsCurrentOrFuture, removeExpiredDatedEvents } from "./runtime-past-event-guard.mjs";

const now = new Date("2026-08-20T08:30:00-04:00");

function event(id, start, end = start, event_type = "event") {
  return { id, event_type, schedule: { start, end, occurrences: [] } };
}

test("hides single-day events from yesterday", () => {
  assert.equal(eventIsCurrentOrFuture(event("past", "2026-08-19T20:00:00-04:00"), {
    now,
    timeZone: "America/Santiago",
  }), false);
});

test("keeps ongoing multi-day events that started earlier", () => {
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
      event("past", "2026-08-19T20:00:00-04:00"),
      event("today", "2026-08-20T20:00:00-04:00"),
      event("ongoing", "2026-08-18", "2026-08-21"),
    ],
  };
  const result = removeExpiredDatedEvents(dataset, { now, timeZone: "America/Santiago" });
  assert.deepEqual(result.events.map((item) => item.id), ["today", "ongoing"]);
});

test("removes past occurrences while keeping the next session of a recurring event", () => {
  const dataset = {
    timezone: "America/Santiago",
    events: [{
      id: "recurring",
      event_type: "event",
      schedule: {
        mode: "multi_session",
        start: "2026-08-18T19:00:00-04:00",
        end: "2026-08-22T20:00:00-04:00",
        display_text: "2026-08-18 · 19:00 · 2026-08-22 · 19:00",
        occurrences: [
          { start: "2026-08-18T19:00:00-04:00", end: "2026-08-18T20:00:00-04:00" },
          { start: "2026-08-22T19:00:00-04:00", end: "2026-08-22T20:00:00-04:00" },
        ],
      },
    }],
  };

  const result = removeExpiredDatedEvents(dataset, { now, timeZone: "America/Santiago" });
  assert.equal(result.events.length, 1);
  assert.equal(result.events[0].schedule.start, "2026-08-22T19:00:00-04:00");
  assert.equal(result.events[0].schedule.end, "2026-08-22T20:00:00-04:00");
  assert.deepEqual(result.events[0].schedule.occurrences, [
    { start: "2026-08-22T19:00:00-04:00", end: "2026-08-22T20:00:00-04:00" },
  ]);
  assert.equal(result.events[0].schedule.display_text, null);
});
