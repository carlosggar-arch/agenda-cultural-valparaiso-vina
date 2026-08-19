import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import { shouldSuppressForTemporalFilter } from "./temporal-priority-core.mjs?v=20260819-temporal1";

let registry = null;
let city = null;
let dataset = null;
let refreshToken = 0;
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

function applyTemporalFilterGuard() {
  guardQueued = false;
  removeLegacyTemporalUi();
  if (!dataset || !city) return;
  const when = activeWhenFilter();
  const byId = new Map((dataset.events || []).map((event) => [String(event?.id || ""), event]));
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

async function refreshDataset() {
  const token = ++refreshToken;
  try {
    registry ||= await loadCityRegistry();
    const cityId = document.documentElement.dataset.city || registry.defaultCityId;
    const nextCity = registry.byId[cityId] || registry.byId[registry.defaultCityId];
    if (!nextCity) return;
    const response = await fetch(nextCity.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    if (token !== refreshToken || !Array.isArray(payload?.events)) return;
    city = nextCity;
    dataset = payload;
    scheduleGuard();
  } catch {
    if (token === refreshToken) {
      city = null;
      dataset = null;
    }
  }
}

removeLegacyTemporalUi();
ensureGuardStyles();
void refreshDataset();

new MutationObserver(() => {
  void refreshDataset();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

document.addEventListener("click", (event) => {
  if (event.target.closest('[data-filter-value], [data-section-filter], [data-filter-clear]')) setTimeout(scheduleGuard, 0);
});
document.addEventListener("input", (event) => {
  if (event.target.matches('[data-smart-search], [data-search], [data-date-from], [data-date-to]')) setTimeout(scheduleGuard, 0);
});
