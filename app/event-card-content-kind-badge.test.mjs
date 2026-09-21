import test from "node:test";
import assert from "node:assert/strict";

import { applyContentKindBadge } from "./event-card-data-quality.mjs";

function badge(text = "Fecha concreta") {
  return {
    textContent: text,
    dataset: {},
    title: "",
    removed: false,
    remove() { this.removed = true; },
    setAttribute() {},
  };
}

function cardWith(existingBadge = null) {
  const meta = {
    appended: null,
    querySelector() { return existingBadge; },
    append(value) { this.appended = value; },
  };
  return {
    dataset: {},
    meta,
    querySelector(selector) {
      return selector === ".card-meta-row" ? meta : null;
    },
  };
}

const city = { id: "valparaiso", timezone: "America/Santiago" };

test("direct and grouped dated cards omit the redundant content-kind badge", () => {
  const event = {
    event_type: "event",
    schedule: { start: "2026-09-06T16:00:00-03:00", end: null, occurrences: [] },
  };
  for (const mode of ["direct", "grouped"]) {
    const legacyBadge = badge();
    const card = cardWith(legacyBadge);
    card.dataset[mode === "direct" ? "eventId" : "eventGroup"] = "event-1";
    assert.equal(applyContentKindBadge(card, event, city), true);
    assert.equal(card.dataset.contentKind, "dated_event");
    assert.equal(legacyBadge.removed, true);
    assert.equal(card.meta.appended, null);
  }
});

test("undated cards retain an accessible pending-date badge", () => {
  const card = cardWith();
  globalThis.document = {
    createElement() {
      const created = badge("");
      created.className = "";
      return created;
    },
  };
  const event = { event_type: "event", schedule: { start: null, end: null, occurrences: [] } };
  assert.equal(applyContentKindBadge(card, event, city), true);
  assert.equal(card.dataset.contentKind, "undated");
  assert.equal(card.meta.appended.textContent, "Fecha por confirmar");
  delete globalThis.document;
});

test("long-running cards remove the retired ongoing badge without changing availability", () => {
  for (const city of [{ id: "valparaiso", timezone: "America/Santiago" }, { id: "gijon", timezone: "Europe/Madrid" }]) {
    const existing = badge("En curso");
    const card = cardWith(existing);
    const event = { event_type: "exhibition", schedule: { start: "2026-09-01", end: "2026-10-31", occurrences: [] } };
    const original = structuredClone(event);
    assert.equal(applyContentKindBadge(card, event, city), true);
    assert.equal(existing.removed, true);
    assert.equal(card.dataset.contentKind, "long_running_event");
    assert.deepEqual(event, original);
  }
});
