import { normalizeTemporalMetadata } from "./temporal-priority-core.mjs?v=20260821-temporal4";
import { filterVisibleDataset } from "./event-lifecycle-core.mjs?v=20260822-lifecycle1";
import { eventForCityPresentation } from "./city-presentation-adapter.mjs?v=20260820-cityui1";
import { normalizeVenueAliases } from "./venue-identity.mjs?v=20260820-venues1";
import { normalizeEventScheduleContract } from "./schedule-contract.mjs?v=20260821-point8-v2";

const STATE_KEY = Symbol.for("vivamos.agendaRuntimeState");
const state = globalThis[STATE_KEY] || (globalThis[STATE_KEY] = { revision: 0, snapshot: null });

function safeCityId(city) {
  return String(city?.id || "").trim();
}

export function publishAgendaRuntimeSnapshot(city, result, now = new Date()) {
  const cityId = safeCityId(city);
  const dataset = result?.dataset;
  if (!cityId || !dataset || !Array.isArray(dataset.events)) return state.snapshot;

  // One shared runtime boundary owns temporal visibility.  This protects users
  // between backend publications: a function that has ended locally disappears
  // even if the last fetched JSON is a few hours old.
  const visibleDataset = filterVisibleDataset(dataset, city, now);
  const normalizedDataset = normalizeTemporalMetadata(visibleDataset, city, now);

  // The shared runtime is the presentation boundary. City adapters may provide
  // corrected raw location facts, but venue-identity is the definitive semantic
  // edge: no adapter/dedupe output can reach cards with a divergent venue alias.
  const adaptedEvents = normalizedDataset.events
    .map((event) => eventForCityPresentation(event, cityId));
  const venueFinalizedEvents = normalizeVenueAliases(adaptedEvents);
  const presentationEvents = venueFinalizedEvents
    .map((event) => normalizeEventScheduleContract(event));
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
