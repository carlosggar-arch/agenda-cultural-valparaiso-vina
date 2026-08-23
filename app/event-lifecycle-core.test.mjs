import assert from "node:assert/strict";
import test from "node:test";

import {
  LIFECYCLE_STATES,
  cityWallClock,
  eventLifecycle,
  filterVisibleDataset,
} from "./runtime-past-event-guard.mjs";

const valpo = { id: "valparaiso", timezone: "America/Santiago" };
const gijon = { id: "gijon", timezone: "Europe/Madrid" };

function event(start, { id = "e1", end = null, occurrences = [] } = {}) {
  return {
    id,
    title: id,
    event_type: "event",
    schedule: {
      start,
      end,
      timezone: "America/Santiago",
      occurrences,
    },
  };
}

function lifecycle(sample, city, now) {
  return eventLifecycle(sample, { now, timeZone: city.timezone });
}

test("22:30 in Chile stays on Aug 22 after UTC crossed midnight", () => {
  const wall = cityWallClock(new Date("2026-08-23T02:30:00Z"), valpo.timezone);
  assert.equal(wall.day, "2026-08-22");
  assert.equal(wall.hour, 22);
  assert.equal(wall.minute, 30);
});

test("timed event remains visible through its entire local calendar day", () => {
  const sample = event("2026-08-22T17:00:00-04:00");
  assert.equal(lifecycle(sample, valpo, new Date("2026-08-22T20:59:00Z")).state, LIFECYCLE_STATES.UPCOMING);
  assert.equal(lifecycle(sample, valpo, new Date("2026-08-22T22:00:00Z")).state, LIFECYCLE_STATES.STARTED);
  assert.equal(lifecycle(sample, valpo, new Date("2026-08-23T03:59:59Z")).state, LIFECYCLE_STATES.STARTED);
  assert.equal(lifecycle(sample, valpo, new Date("2026-08-23T04:00:00Z")).state, LIFECYCLE_STATES.ENDED);
});

test("earlier and later occurrences from today keep a multi-function event visible", () => {
  const sample = event("2026-08-22T15:00:00-04:00", {
    occurrences: [
      { start: "2026-08-22T15:00:00-04:00", end: null },
      { start: "2026-08-22T21:00:00-04:00", end: null },
    ],
  });
  const state = lifecycle(sample, valpo, new Date("2026-08-23T00:30:00Z"));
  assert.equal(state.state, LIFECYCLE_STATES.STARTED);
  assert.equal(state.visible, true);
});

test("runtime keeps earlier and later events from the current local day", () => {
  const dataset = {
    timezone: "America/Santiago",
    events: [
      event("2026-08-22T15:00:00-04:00", { id: "ended" }),
      event("2026-08-22T21:00:00-04:00", { id: "future" }),
    ],
  };
  const filtered = filterVisibleDataset(dataset, valpo, new Date("2026-08-23T00:30:00Z"));
  assert.deepEqual(filtered.events.map((item) => item.id), ["ended", "future"]);
});

test("date-only event remains visible through its local final day", () => {
  const sample = event("2026-08-22", { end: "2026-08-22" });
  assert.equal(
    lifecycle(sample, valpo, new Date("2026-08-23T02:30:00Z")).state,
    LIFECYCLE_STATES.ONGOING,
  );
  assert.equal(
    lifecycle(sample, valpo, new Date("2026-08-23T04:30:00Z")).state,
    LIFECYCLE_STATES.ENDED,
  );
});

test("timed start with a later date-only end remains visible through the final local day", () => {
  const sample = event("2026-08-20T11:00:00-04:00", {
    id: "Cráneos, esenciales para la vida",
    end: "2026-12-31",
  });

  const duringRange = lifecycle(sample, valpo, new Date("2026-08-23T14:30:00Z"));
  assert.equal(duringRange.state, LIFECYCLE_STATES.ONGOING);
  assert.equal(duringRange.visible, true);
  assert.equal(duringRange.endDay, "2026-12-31");

  assert.equal(
    lifecycle(sample, valpo, new Date("2027-01-01T04:30:00Z")).state,
    LIFECYCLE_STATES.ENDED,
  );
});

test("timed start with a same-day date-only end remains visible through that local day", () => {
  const sample = event("2026-08-23T10:00:00-04:00", { end: "2026-08-23" });
  assert.equal(
    lifecycle(sample, valpo, new Date("2026-08-23T17:59:00Z")).state,
    LIFECYCLE_STATES.STARTED,
  );
  assert.equal(
    lifecycle(sample, valpo, new Date("2026-08-24T03:59:59Z")).state,
    LIFECYCLE_STATES.STARTED,
  );
  assert.equal(lifecycle(sample, valpo, new Date("2026-08-24T04:00:00Z")).state, LIFECYCLE_STATES.ENDED);
});

test("IANA timezone handles Chile DST transition", () => {
  const before = cityWallClock(new Date("2026-09-06T03:30:00Z"), valpo.timezone);
  const after = cityWallClock(new Date("2026-09-06T04:30:00Z"), valpo.timezone);
  assert.equal(before.day, "2026-09-05");
  assert.equal(before.hour, 23);
  assert.equal(after.day, "2026-09-06");
  assert.equal(after.hour, 1);
});

test("same lifecycle works with Europe/Madrid", () => {
  const sample = {
    ...event("2026-08-23T20:00:00+02:00"),
    schedule: {
      start: "2026-08-23T20:00:00+02:00",
      end: null,
      timezone: "Europe/Madrid",
      occurrences: [],
    },
  };
  assert.equal(lifecycle(sample, gijon, new Date("2026-08-23T17:00:00Z")).state, LIFECYCLE_STATES.UPCOMING);
  assert.equal(lifecycle(sample, gijon, new Date("2026-08-23T19:00:00Z")).state, LIFECYCLE_STATES.STARTED);
  assert.equal(lifecycle(sample, gijon, new Date("2026-08-23T21:59:59Z")).state, LIFECYCLE_STATES.STARTED);
  assert.equal(lifecycle(sample, gijon, new Date("2026-08-23T22:00:00Z")).state, LIFECYCLE_STATES.ENDED);
});
