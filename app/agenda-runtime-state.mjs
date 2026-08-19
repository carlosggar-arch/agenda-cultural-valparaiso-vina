let revision = 0;
let snapshot = null;

function safeCityId(city) {
  return String(city?.id || "").trim();
}

export function publishAgendaRuntimeSnapshot(city, result) {
  const cityId = safeCityId(city);
  const dataset = result?.dataset;
  if (!cityId || !dataset || !Array.isArray(dataset.events)) return snapshot;

  snapshot = {
    cityId,
    city,
    dataset,
    events: dataset.events,
    secondaryPrograms: Array.isArray(result?.secondaryPrograms) ? result.secondaryPrograms : [],
    hiddenPrograms: Array.isArray(result?.hiddenPrograms) ? result.hiddenPrograms : [],
    diagnostics: Array.isArray(result?.diagnostics) ? result.diagnostics : [],
    revision: ++revision,
  };

  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("vivamos:agenda-data-ready", {
      detail: {
        cityId,
        revision: snapshot.revision,
        eventCount: snapshot.events.length,
      },
    }));
  }
  return snapshot;
}

export function getAgendaRuntimeSnapshot(cityId = null) {
  if (!snapshot) return null;
  if (cityId && snapshot.cityId !== String(cityId)) return null;
  return snapshot;
}

export function clearAgendaRuntimeSnapshot() {
  snapshot = null;
}
