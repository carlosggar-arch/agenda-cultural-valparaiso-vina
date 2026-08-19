import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import { shouldSuppressForTemporalFilter } from "./temporal-priority-core.mjs?v=20260819-temporal1";

const CITY_REGISTRY = await loadCityRegistry();
const CITY_CONFIG = CITY_REGISTRY.byId;
const DEFAULT_CITY_ID = CITY_REGISTRY.defaultCityId;

let dataset = null;
let city = null;
let loadingToken = 0;
let applyingGuard = false;

function currentCity() {
  const id = document.documentElement.dataset.city;
  return CITY_CONFIG[id] || CITY_CONFIG[DEFAULT_CITY_ID] || null;
}

function activeWhenFilter() {
  const visible = document.querySelector('[data-combined-when] [data-filter-value].active');
  if (visible?.dataset?.filterValue) return visible.dataset.filterValue;
  const legacy = document.querySelector('[data-section-filters] [data-section-filter].active');
  return legacy?.dataset?.sectionFilter || "todos";
}

function eventMap() {
  return new Map((dataset?.events || []).map((event) => [String(event?.id || ""), event]));
}

function ensureGuardStyles() {
  if (document.querySelector("style[data-temporal-filter-guard-styles]")) return;
  const style = document.createElement("style");
  style.dataset.temporalFilterGuardStyles = "";
  style.textContent = '.event-card[data-temporal-suppressed="true"]{display:none!important}';
  document.head.append(style);
}

function removeLegacyTemporalUi() {
  document.querySelectorAll("[data-temporal-priority], style[data-temporal-priority-styles], .temporal-urgency-badge")
    .forEach((node) => node.remove());
}

function applyTemporalFilterGuard() {
  if (applyingGuard || !dataset || !city) return;
  applyingGuard = true;
  try {
    removeLegacyTemporalUi();
    const when = activeWhenFilter();
    const byId = eventMap();

    for (const card of document.querySelectorAll('[data-agenda] .event-card[data-event-id]')) {
      const item = byId.get(String(card.dataset.eventId || ""));
      const suppress = item ? shouldSuppressForTemporalFilter(item, when) : false;
      if (suppress) card.dataset.temporalSuppressed = "true";
      else delete card.dataset.temporalSuppressed;
    }

    if (when !== "todos") {
      const visibleDated = document.querySelectorAll('[data-dated-grid] .event-card:not([data-temporal-suppressed="true"])').length;
      const datedTotal = document.querySelector("[data-dated-total]");
      if (datedTotal && datedTotal.textContent !== String(visibleDated)) datedTotal.textContent = String(visibleDated);

      const total = document.querySelector("[data-total]");
      const visiblePrograms = document.querySelectorAll('[data-program-grid] .event-card:not([data-temporal-suppressed="true"])').length;
      const visibleFlexible = document.querySelectorAll('[data-flexible-grid] .event-card:not([data-temporal-suppressed="true"])').length;
      const visibleTotal = String(visibleDated + visiblePrograms + visibleFlexible);
      if (total && total.textContent !== visibleTotal) total.textContent = visibleTotal;
    }
  } finally {
    applyingGuard = false;
  }
}

function scheduleGuard() {
  queueMicrotask(applyTemporalFilterGuard);
}

async function loadDatasetForCity(nextCity) {
  const token = ++loadingToken;
  city = nextCity;
  dataset = null;
  try {
    const response = await fetch(nextCity.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (token !== loadingToken) return;
    if (!Array.isArray(payload?.events)) throw new Error("Dataset inválido");
    dataset = payload;
    scheduleGuard();
  } catch {
    if (token !== loadingToken) return;
    dataset = null;
  }
}

function refreshCity() {
  const next = currentCity();
  if (!next || next.id === city?.id) return;
  loadDatasetForCity(next);
}

removeLegacyTemporalUi();
ensureGuardStyles();
refreshCity();

new MutationObserver(() => scheduleGuard()).observe(document.querySelector("[data-agenda]") || document.body, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["class", "data-event-id"],
});
new MutationObserver(refreshCity).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-city"],
});
document.addEventListener("click", (event) => {
  if (event.target.closest("[data-filter-value], [data-section-filter], [data-category-filter]")) scheduleGuard();
}, true);
document.addEventListener("input", (event) => {
  if (event.target.matches("[data-smart-search], [data-search], [data-date-from], [data-date-to]")) scheduleGuard();
}, true);
