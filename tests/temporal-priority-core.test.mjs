import test from "node:test";
import assert from "node:assert/strict";
import {
  classifyContentKind,
  classifyTemporalEvent,
  compareTemporalPriority,
  normalizeTemporalMetadata,
  organizeTemporalPriority,
  temporalBadge,
  shouldSuppressForTemporalFilter,
  weekendBounds,
} from "../app/temporal-priority-core.mjs";

const valpo = { timezone: "America/Santiago", locale: "es-CL" };
const gijon = { timezone: "Europe/Madrid", locale: "es-ES" };
const now = new Date("2026-08-21T12:00:00Z");

function event(id, start, end = null, options = {}) {
  return {
    id,
    title: options.title || id,
    event_type: options.eventType || "event",
    primary_category: {
      id: options.category || "musica",
      label: options.category === "exposiciones" ? "Exposiciones" : "Música",
    },
    categories: [],
    description: options.description || "",
    tags: options.tags || [],
    schedule: {
      mode: options.mode || "dated",
      start,
      end,
      display_text: options.displayText || "",
      start_confidence: options.startConfidence,
      end_confidence: options.endConfidence,
      occurrences: options.occurrences || [],
    },
  };
}

test("technical fallback never creates a false Hoy", () => {
  const item = event("fallback", "2026-08-21", "2026-08-30", {
    category: "exposiciones",
    startConfidence: "technical_fallback",
    endConfidence: "explicit",
  });
  const blocks = organizeTemporalPriority([item], valpo, now);
  assert.deepEqual(blocks.today, []);
  assert.equal(classifyTemporalEvent(item, valpo, now).bucket, "ongoing");
  assert.equal(temporalBadge(item, valpo, now), null);
  assert.equal(shouldSuppressForTemporalFilter(item, "hoy"), true);
});

test("missing confidence can classify a usable date without creating a badge", () => {
  const item = event("missing-confidence", "2026-08-21", null);
  const blocks = organizeTemporalPriority([item], valpo, now);
  assert.equal(blocks.today[0]?.id, "missing-confidence");
  assert.equal(temporalBadge(item, valpo, now), null);
  assert.equal(shouldSuppressForTemporalFilter(item, "hoy"), false);
});

test("long temporary event is not a permanent offer", () => {
  const exhibition = event("long", "2026-08-01", "2026-09-30", { category: "exposiciones" });
  const permanent = event("permanent", null, null, {
    eventType: "flexible_offer",
    mode: "flexible",
    displayText: "Horario flexible, a convenir",
  });
  assert.equal(classifyContentKind(exhibition, valpo), "long_running_event");
  assert.equal(classifyContentKind(permanent, valpo), "permanent_offer");
});

test("weekly flexible offer becomes recurring and always available", () => {
  const item = event("salsa", null, null, {
    eventType: "flexible_offer",
    mode: "flexible",
    displayText: "Lunes a viernes, desde las 18:20",
  });
  const state = classifyTemporalEvent(item, valpo, now);
  assert.equal(state.contentKind, "recurring_offer");
  assert.equal(state.bucket, "always_available");
});

test("finite recurring-looking course remains a long-running event", () => {
  const item = event("course", "2026-08-01", "2026-08-31", {
    description: "Curso todos los viernes durante agosto",
  });
  assert.equal(classifyContentKind(item, valpo), "long_running_event");
});

test("weekend is exactly Friday Saturday Sunday", () => {
  assert.deepEqual(weekendBounds("2026-08-19"), { start: "2026-08-21", end: "2026-08-23" });
  assert.deepEqual(weekendBounds("2026-08-22"), { start: "2026-08-21", end: "2026-08-23" });
  const friday = event("friday", "2026-08-21", null);
  const saturday = event("saturday", "2026-08-22", null);
  const sunday = event("sunday", "2026-08-23", null);
  assert.equal(classifyTemporalEvent(friday, valpo, now).bucket, "today");
  assert.equal(classifyTemporalEvent(saturday, valpo, now).bucket, "this_weekend");
  assert.equal(classifyTemporalEvent(sunday, valpo, now).bucket, "this_weekend");
});

test("long active event is ongoing unless it ends soon", () => {
  const ongoing = event("ongoing", "2026-08-01", "2026-09-30");
  const ending = event("ending", "2026-08-01", "2026-08-25");
  assert.equal(classifyTemporalEvent(ongoing, valpo, now).bucket, "ongoing");
  assert.equal(classifyTemporalEvent(ending, valpo, now).bucket, "ending_soon");
});

test("single-date event outranks long-running content in the same weekend", () => {
  const long = event("long", "2026-08-22", "2026-09-30", { category: "exposiciones" });
  const concert = event("concert", "2026-08-22", null);
  assert.ok(compareTemporalPriority(concert, long, valpo, now) < 0);
  const blocks = organizeTemporalPriority([long, concert], valpo, now);
  assert.deepEqual(blocks.thisWeekend.map((item) => item.id), ["concert", "long"]);
});

test("hierarchy no longer follows oldest start date", () => {
  const oldOngoing = event("old-ongoing", "2026-07-01", "2026-10-01");
  const saturday = event("saturday", "2026-08-22", null);
  const sorted = [oldOngoing, saturday].sort((a, b) => compareTemporalPriority(a, b, valpo, now));
  assert.deepEqual(sorted.map((item) => item.id), ["saturday", "old-ongoing"]);
});

test("runtime normalizer writes content_kind and temporal_bucket", () => {
  const dataset = { events: [event("saturday", "2026-08-22", null)] };
  const normalized = normalizeTemporalMetadata(dataset, valpo, now);
  assert.equal(normalized.events[0].content_kind, "dated_event");
  assert.equal(normalized.events[0].temporal_bucket, "this_weekend");
});

test("city timezone still controls Today", () => {
  const instant = new Date("2026-08-19T00:30:00Z");
  const item = event("gijon-today", "2026-08-19", null, { startConfidence: "explicit" });
  assert.equal(classifyTemporalEvent(item, gijon, instant).bucket, "today");
  assert.notEqual(classifyTemporalEvent(item, valpo, instant).bucket, "today");
});
