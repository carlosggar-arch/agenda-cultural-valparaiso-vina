import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";
import { shouldSuppressForTemporalFilter } from "./temporal-priority-core.mjs?v=20260819-temporal1";

let snapshot = null;
let guardQueued = false;

function removeLegacyTemporalUi() {
  document.querySelectorAll("[data-temporal-priority], style[data-temporal-priority-styles], .temporal-urgency-badge")
    .forEach((node) => node.remove());
}

function ensureGuardStyles() {
  if (document.querySelector("style[data-temporal-filter-guard-styles]")) return;
  const style = document.createElement("style");
  style.dataset.temporalFilterGuardStyles = "";
  style.textContent = '.event-card[data-temporal-suppressed="true"]{display:none!important}';
  document.head.append(style);
}

function activeWhenFilter() {
  const visible = document.querySelector('[data-combined-when] [data-filter-value].active');
  if (visible?.dataset?.filterValue) return visible.dataset.filterValue;
  const legacy = document.querySelector('[data-section-filters] [data-section-filter].active');
  return legacy?.dataset?.sectionFilter || "todos";
}

function syncSnapshot() {
  const cityId = String(document.documentElement.dataset.city || "").trim();
  const next = getAgendaRuntimeSnapshot(cityId || null);
  if (!next) return false;
  snapshot = next;
  return true;
}

function applyTemporalFilterGuard() {
  guardQueued = false;
  removeLegacyTemporalUi();
  if (!syncSnapshot()) return;
  const when = activeWhenFilter();
  const byId = new Map((snapshot.events || []).map((event) => [String(event?.id || ""), event]));
  for (const card of document.querySelectorAll('[data-agenda] .event-card[data-event-id]')) {
    const item = byId.get(String(card.dataset.eventId || ""));
    const suppress = item ? shouldSuppressForTemporalFilter(item, when) : false;
    if (suppress) card.dataset.temporalSuppressed = "true";
    else delete card.dataset.temporalSuppressed;
  }
}

function scheduleGuard() {
  if (guardQueued) return;
  guardQueued = true;
  queueMicrotask(applyTemporalFilterGuard);
}

removeLegacyTemporalUi();
ensureGuardStyles();
scheduleGuard();

for (const eventName of ["vivamos:agenda-data-ready", "vivamos:agenda-rendered", "vivamos:core-ready"]) {
  window.addEventListener(eventName, scheduleGuard);
}
new MutationObserver(scheduleGuard).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-city"],
});

document.addEventListener("click", (event) => {
  if (event.target.closest('[data-filter-value], [data-section-filter], [data-filter-clear]')) setTimeout(scheduleGuard, 0);
});
document.addEventListener("input", (event) => {
  if (event.target.matches('[data-smart-search], [data-search], [data-date-from], [data-date-to]')) setTimeout(scheduleGuard, 0);
});
