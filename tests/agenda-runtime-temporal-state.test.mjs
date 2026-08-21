import test from "node:test";
import assert from "node:assert/strict";

const city = { id: "valparaiso", timezone: "America/Santiago", locale: "es-CL" };

function recurringOffer() {
  return {
    id: "recurring-offer",
    title: "Clases de salsa",
    event_type: "flexible_offer",
    primary_category: { id: "cursos-talleres-campus", label: "Cursos, talleres y experiencias" },
    categories: [],
    schedule: {
      mode: "flexible",
      start: null,
      end: null,
      display_text: "Lunes a viernes, desde las 18:20",
      occurrences: [],
    },
  };
}

test("runtime snapshot is shared across versioned module identities", async () => {
  const writer = await import("../app/agenda-runtime-state.mjs?runtime-writer");
  const reader = await import("../app/agenda-runtime-state.mjs?runtime-reader");
  writer.clearAgendaRuntimeSnapshot();

  const result = { dataset: { events: [recurringOffer()] }, diagnostics: [] };
  writer.publishAgendaRuntimeSnapshot(city, result);

  const snapshot = reader.getAgendaRuntimeSnapshot("valparaiso");
  assert.ok(snapshot);
  assert.equal(snapshot.events[0].content_kind, "recurring_offer");
  assert.equal(snapshot.events[0].temporal_bucket, "always_available");
  assert.equal(result.dataset.events[0].content_kind, "recurring_offer");
  assert.equal(result.dataset.events[0].temporal_bucket, "always_available");
});
