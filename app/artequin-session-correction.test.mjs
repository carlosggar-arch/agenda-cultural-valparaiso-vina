import assert from "node:assert/strict";
import { correctArtequinNaturalArtSessions } from "./artequin-session-correction.js";
import { loadAgendaDataset } from "./data-pipeline.js";

const WRONG_EVENT = {
  id: "agenda_650e95f9b205b8665b0bce6d",
  title: "Ciclo taller EL ARTE ES NATURAL",
  event_type: "event",
  source_id: "artequin_vina",
  source_name: "Artequin Viña del Mar",
  primary_category: { id: "cursos-talleres", label: "Cursos y talleres" },
  categories: [{ id: "cursos-talleres", label: "Cursos y talleres" }],
  schedule: {
    mode: "multi_day",
    start: "2026-08-18T15:00:00-04:00",
    end: "2026-08-28",
    timezone: "America/Santiago",
    display_text: "2026-08-18 · 15:00, 16:00",
    occurrences: [],
  },
  location: { venue: "Museo Artequin Viña del Mar", city: "Viña del Mar" },
  price: { is_free: false, currency: "CLP", min_amount: 3000, max_amount: 10000, display_text: "$3.000 · $10.000" },
  links: { official: "https://artequinvina.cl/" },
};

{
  const corrected = correctArtequinNaturalArtSessions({ events: [WRONG_EVENT] });
  const event = corrected.events[0];
  assert.equal(event.schedule.mode, "multi_session");
  assert.deepEqual(event.schedule.occurrences.map((item) => item.start), [
    "2026-08-07T15:00:00-04:00",
    "2026-08-14T15:00:00-04:00",
    "2026-08-21T15:00:00-04:00",
    "2026-08-28T15:00:00-04:00",
  ]);
  assert.equal(event.schedule.end, "2026-08-28T16:00:00-04:00");
}

{
  const fetchImpl = async () => ({
    ok: true,
    status: 200,
    async json() {
      return { counts: { total: 1, events: 1, programs: 0 }, events: [WRONG_EVENT] };
    },
  });
  const result = await loadAgendaDataset(
    { id: "valparaiso", dataset: "base.json", timezone: "America/Santiago" },
    { fetchImpl, now: new Date("2026-08-20T04:30:00-04:00") },
  );
  const event = result.dataset.events.find((item) => item.id === WRONG_EVENT.id);
  assert.ok(event, "Artequin event must remain available for its future Friday sessions");
  assert.equal(event.event_type, "event");
  assert.equal(event.schedule.mode, "multi_session");
  assert.equal(event.schedule.start, "2026-08-21T15:00:00-04:00");
  assert.equal(event.schedule.end, "2026-08-28T16:00:00-04:00");
  assert.equal(event.schedule.display_text, null, "expired Friday sessions must be removed from the displayed schedule");
  assert.deepEqual(event.schedule.occurrences.map((item) => item.start), [
    "2026-08-21T15:00:00-04:00",
    "2026-08-28T15:00:00-04:00",
  ]);
  assert.equal(result.diagnostics.find((stage) => stage.name === "artequin-session-correction")?.status, "ok");
}

console.log("ARTEQUIN_SESSION_CORRECTION_OK");
