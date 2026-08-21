import { normalizeTemporalMetadata } from "./temporal-priority-core.mjs?v=20260821-temporal4";
import { eventForCityPresentation } from "./city-presentation-adapter.mjs?v=20260820-cityui1";

const STATE_KEY = Symbol.for("vivamos.agendaRuntimeState");
const state = globalThis[STATE_KEY] || (globalThis[STATE_KEY] = { revision: 0, snapshot: null });

function safeCityId(city) {
  return String(city?.id || "").trim();
}

export function publishAgendaRuntimeSnapshot(city, result) {
  const cityId = safeCityId(city);
  const dataset = result?.dataset;
  if (!cityId || !dataset || !Array.isArray(dataset.events)) return state.snapshot;

  const normalizedDataset = normalizeTemporalMetadata(dataset, city, new Date());

  // The shared runtime is the presentation boundary. City differences are
  // expressed through adapters here, never by selecting a different renderer.
  const presentationEvents = normalizedDataset.events.map((event) => eventForCityPresentation(event, cityId));
  const presentationDataset = { ...normalizedDataset, events: presentationEvents };

  // loadAgendaDataset callers (including app-core and filters) must see the same
  // adapted event objects as every optional presentation module. This prevents a
  // raw city-specific value from flashing first and being repaired by a second
  // renderer later in the frame.
  result.dataset = presentationDataset;

  state.snapshot = {
    cityId,
    city,
    dataset: presentationDataset,
    events: presentationEvents,
    secondaryPrograms: Array.isArray(result?.secondaryPrograms) ? result.secondaryPrograms : [],
    hiddenPrograms: Array.isArray(result?.hiddenPrograms) ? result.hiddenPrograms : [],
    diagnostics: Array.isArray(result?.diagnostics) ? result.diagnostics : [],
    revision: ++state.revision,
  };

  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("vivamos:agenda-data-ready", {
      detail: {
        cityId,
        revision: state.snapshot.revision,
        eventCount: state.snapshot.events.length,
      },
    }));
  }
  return state.snapshot;
}

export function getAgendaRuntimeSnapshot(cityId = null) {
  if (!state.snapshot) return null;
  if (cityId && state.snapshot.cityId !== String(cityId)) return null;
  return state.snapshot;
}

export function clearAgendaRuntimeSnapshot() {
  state.snapshot = null;
}
