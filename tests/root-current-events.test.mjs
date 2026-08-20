import assert from "node:assert/strict";
import test from "node:test";

import {
  defaultFilterState,
  eventIsCurrentOrFuture,
  eventsForSection,
  fetchDataset,
  filterEvents,
} from "../assets/agenda-core.mjs";

const NOW = new Date("2026-08-19T20:21:00-04:00");

function event(id, start, end = start, event_type = "event") {
  return {
    id,
    title: id,
    event_type,
    categories: [{ id: "cine", label: "Cine" }],
    primary_category: { id: "cine", label: "Cine" },
    schedule: { start, end, occurrences: [] },
    location: { city: "Valparaíso", venue: "Sala" },
    price: { is_free: true, display_text: "Gratis" },
    links: {},
    public_status: {},
  };
}

test("root web hides a dated event that ended yesterday", () => {
  assert.equal(eventIsCurrentOrFuture(event("ayer", "2026-08-18T20:00:00-04:00"), NOW), false);
});

test("root web keeps an ongoing range that started yesterday", () => {
  assert.equal(eventIsCurrentOrFuture(event("en-curso", "2026-08-18", "2026-08-21"), NOW), true);
});

test("root web keeps future events and non-dated public program types", () => {
  assert.equal(eventIsCurrentOrFuture(event("fantasmas", "2026-08-22T22:00:00-04:00"), NOW), true);
  assert.equal(eventIsCurrentOrFuture(event("programa", "2026-08-01", "2026-08-31", "program"), NOW), true);
  assert.equal(eventIsCurrentOrFuture(event("flexible", null, null, "flexible_offer"), NOW), true);
});

test("unbounded root filters cannot reintroduce yesterday events", () => {
  const events = [
    event("ayer", "2026-08-18T20:00:00-04:00"),
    event("hoy", "2026-08-19T21:00:00-04:00"),
    event("fantasmas", "2026-08-22T22:00:00-04:00"),
  ];
  assert.deepEqual(
    filterEvents(events, defaultFilterState(), NOW).map((item) => item.id),
    ["hoy", "fantasmas"],
  );
  assert.deepEqual(
    eventsForSection(events, "gratis", NOW).map((item) => item.id),
    ["hoy", "fantasmas"],
  );
});

test("root dataset request bypasses browser HTTP cache", async () => {
  let options;
  const fetchImplementation = async (_path, receivedOptions) => {
    options = receivedOptions;
    return {
      ok: true,
      async json() {
        return {
          schema_version: "1.2.0",
          events: [event("fantasmas", "2026-08-22T22:00:00-04:00")],
        };
      },
    };
  };
  const dataset = await fetchDataset(fetchImplementation, "./agenda_web.json");
  assert.equal(dataset.events[0].id, "fantasmas");
  assert.equal(options?.cache, "no-store");
});
