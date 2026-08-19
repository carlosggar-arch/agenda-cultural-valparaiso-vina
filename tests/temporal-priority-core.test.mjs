import test from "node:test";
import assert from "node:assert/strict";
import {
  organizeTemporalPriority,
  temporalBadge,
  shouldSuppressForTemporalFilter,
} from "../app/temporal-priority-core.mjs";

const valpo = { timezone: "America/Santiago", locale: "es-CL" };
const gijon = { timezone: "Europe/Madrid", locale: "es-ES" };
const now = new Date("2026-08-19T12:00:00Z");

function event(id, start, end = null, options = {}) {
  return {
    id,
    title: id,
    event_type: "event",
    primary_category: { id: options.category || "musica", label: options.category === "exposiciones" ? "Exposiciones" : "Música" },
    categories: [],
    schedule: {
      start,
      end,
      start_confidence: options.startConfidence,
      end_confidence: options.endConfidence,
      occurrences: options.occurrences || [],
    },
  };
}

test("technical fallback never creates a false Hoy", () => {
  const item = event("fallback", "2026-08-19", "2026-08-30", {
    category: "exposiciones",
    startConfidence: "technical_fallback",
    endConfidence: "explicit",
  });
  const blocks = organizeTemporalPriority([item], valpo, now);
  assert.deepEqual(blocks.today, []);
  assert.equal(temporalBadge(item, valpo, now), null);
  assert.equal(shouldSuppressForTemporalFilter(item, "hoy"), true);
});

test("missing confidence stays conservative for badges but does not hide a dated event", () => {
  const item = event("missing-confidence", "2026-08-19", null);
  const blocks = organizeTemporalPriority([item], valpo, now);
  assert.deepEqual(blocks.today, []);
  assert.equal(temporalBadge(item, valpo, now), null);
  assert.equal(shouldSuppressForTemporalFilter(item, "hoy"), false);
  assert.equal(shouldSuppressForTemporalFilter(item, "7-dias"), false);
});

test("reliable explicit start creates Hoy", () => {
  const item = event("today", "2026-08-19T20:00:00-04:00", null, { startConfidence: "explicit" });
  const blocks = organizeTemporalPriority([item], valpo, now);
  assert.equal(blocks.today[0]?.id, "today");
  assert.equal(temporalBadge(item, valpo, now), "Hoy");
});

test("reliable close within three days gets ending urgency", () => {
  const item = event("closing", "2026-08-01", "2026-08-21", {
    startConfidence: "technical_fallback",
    endConfidence: "official_revalidation",
  });
  const blocks = organizeTemporalPriority([item], valpo, now);
  assert.equal(blocks.endingSoon[0]?.id, "closing");
  assert.equal(temporalBadge(item, valpo, now), "Últimos 3 días");
  assert.equal(shouldSuppressForTemporalFilter(item, "terminan-pronto"), false);
});

test("missing end confidence does not erase an otherwise valid ending filter candidate", () => {
  const item = event("closing-without-confidence", "2026-08-01", "2026-08-21", {
    startConfidence: "explicit",
  });
  assert.equal(shouldSuppressForTemporalFilter(item, "terminan-pronto"), false);
});

test("unreliable close never creates endingSoon or closing badge", () => {
  const item = event("bad-end", "2026-08-01", "2026-08-21", {
    startConfidence: "explicit",
    endConfidence: "technical_fallback",
  });
  const blocks = organizeTemporalPriority([item], valpo, now);
  assert.deepEqual(blocks.endingSoon, []);
  assert.equal(temporalBadge(item, valpo, now), null);
  assert.equal(shouldSuppressForTemporalFilter(item, "terminan-pronto"), true);
});

test("long current exhibition stays in the exhibition block", () => {
  const item = event("museum", "2026-08-19", "2026-09-30", {
    category: "exposiciones",
    startConfidence: "technical_fallback",
    endConfidence: "explicit",
  });
  const blocks = organizeTemporalPriority([item], valpo, now);
  assert.equal(blocks.exhibitions[0]?.id, "museum");
  assert.deepEqual(blocks.upcoming, []);
});

test("upcoming block contains punctual events, not future exhibitions", () => {
  const concert = event("concert", "2026-08-22T20:00:00-04:00", null, { startConfidence: "official_visible_schedule" });
  const exhibition = event("future-exhibition", "2026-08-22", "2026-09-10", {
    category: "exposiciones",
    startConfidence: "explicit",
    endConfidence: "explicit",
  });
  const blocks = organizeTemporalPriority([concert, exhibition], valpo, now);
  assert.equal(blocks.upcoming[0]?.id, "concert");
  assert.equal(blocks.upcoming.some((item) => item.id === "future-exhibition"), false);
});

test("city timezone controls the meaning of Hoy", () => {
  const instant = new Date("2026-08-19T00:30:00Z");
  const item = event("gijon-today", "2026-08-19", null, { startConfidence: "explicit" });
  assert.equal(organizeTemporalPriority([item], gijon, instant).today.length, 1);
  assert.equal(organizeTemporalPriority([item], valpo, instant).today.length, 0);
});
