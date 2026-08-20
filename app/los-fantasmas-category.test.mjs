import assert from "node:assert/strict";
import test from "node:test";

import { loadAgendaDataset } from "./data-pipeline.js";

const TEST_NOW = new Date("2026-08-19T12:00:00-04:00");
const EVENT_ID = "agenda_bc147abef119a17edb8a9770";

function response(payload) {
  return {
    ok: true,
    status: 200,
    async json() { return payload; },
  };
}

test("PWA keeps Los Fantasmas as Cine and adds Teatro for discoverability", async () => {
  const losFantasmas = {
    id: EVENT_ID,
    title: "Los Fantasmas",
    event_type: "event",
    source_id: "teatro_la_peste",
    source_name: "Teatro La Peste",
    primary_category: { id: "cine", label: "Cine" },
    categories: [{ id: "cine", label: "Cine" }],
    schedule: {
      start: "2026-08-22T22:00:00-04:00",
      end: "2026-08-22T23:30:00-04:00",
      occurrences: [],
    },
    location: {
      venue: "Centro de Investigación Teatro La Peste",
      city: "Valparaíso",
    },
    price: { is_free: true, display_text: "Gratis" },
    links: { official: "https://www.instagram.com/p/DNbKM5_vI_8/" },
  };
  const fetchImpl = async () => response({
    counts: { total: 1, events: 1, programs: 0 },
    events: [losFantasmas],
  });

  const result = await loadAgendaDataset(
    { id: "valparaiso", dataset: "base.json", timezone: "America/Santiago" },
    { fetchImpl, now: TEST_NOW },
  );
  const published = result.dataset.events.find((event) => event.id === EVENT_ID);

  assert.ok(published);
  assert.equal(published.primary_category.id, "cine");
  assert.deepEqual(published.categories.map((category) => category.id), ["cine", "teatro"]);
  assert.equal(result.diagnostics.find((stage) => stage.name === "known-publication-categories")?.status, "ok");
});
