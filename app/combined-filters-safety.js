const FILTER_PARAMS = ["when", "area", "access", "format", "aud", "cat", "q", "from", "to", "price"];

let lastCity = String(document.documentElement.dataset.city || "");
let repairTimer = null;

function pressedFilterValue(selector, fallback = "todos") {
  const button = document.querySelector(`${selector} [data-filter-value][aria-pressed="true"]`)
    || document.querySelector(`${selector} [data-filter-value].active`);
  return String(button?.dataset?.filterValue || fallback).trim() || fallback;
}

function currentFilterStateIsNeutral() {
  // Live controls change before history.replaceState, so they are authoritative.
  // Otherwise the startup fail-open can briefly mistake an active date for a
  // neutral state and unhide cards from the previous day.
  if (pressedFilterValue("[data-combined-when]") !== "todos") return false;
  if (pressedFilterValue("[data-combined-area]") !== "todos") return false;
  if (document.querySelectorAll('[data-combined-category-filters] [data-combined-category].active').length) return false;
  if (String(document.querySelector('[data-smart-search]')?.value || "").trim()) return false;
  if (String(document.querySelector('[data-date-from]')?.value || "").trim()) return false;
  if (String(document.querySelector('[data-date-to]')?.value || "").trim()) return false;

  const params = new URLSearchParams(window.location.search);
  for (const key of FILTER_PARAMS) {
    const value = String(params.get(key) || "").trim();
    if (!value) continue;
    if (["when", "area", "access", "format", "aud"].includes(key) && value === "todos") continue;
    return false;
  }
  return true;
}

function resetContextualUrlState() {
  const url = new URL(window.location.href);
  let changed = false;
  for (const key of FILTER_PARAMS) {
    if (!url.searchParams.has(key)) continue;
    url.searchParams.delete(key);
    changed = true;
  }
  if (changed) history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function repairNeutralAgendaVisibility() {
  repairTimer = null;
  if (!currentFilterStateIsNeutral()) return;

  const grid = document.querySelector('[data-dated-grid]');
  if (!grid) return;
  const directCards = [...grid.querySelectorAll('.event-card[data-event-id]')];
  if (!directCards.length || directCards.some((card) => !card.hidden)) return;

  // Fail open only when the interface is genuinely neutral. Active filters
  // always win over this recovery layer.
  for (const card of directCards) card.hidden = false;
  for (const sentinel of document.querySelectorAll('[data-static-exhibition-sentinels] .event-card[data-event-id]')) sentinel.hidden = false;
  for (const grouped of grid.querySelectorAll('.event-card[data-event-group]')) grouped.hidden = false;

  const section = document.querySelector('[data-dated-section]');
  if (section) section.hidden = false;

  document.documentElement.dataset.filterFailOpen = "true";
  window.dispatchEvent(new CustomEvent("vivamos:filter-fail-open", {
    detail: { city: document.documentElement.dataset.city || "", restored: directCards.length },
  }));
}

function queueVisibilityRepair(delay = 0) {
  if (repairTimer) clearTimeout(repairTimer);
  repairTimer = setTimeout(() => requestAnimationFrame(repairNeutralAgendaVisibility), delay);
}

// Bounded startup retries; deliberately no grid observer.
queueVisibilityRepair(0);
setTimeout(() => queueVisibilityRepair(0), 350);
setTimeout(() => queueVisibilityRepair(0), 900);

new MutationObserver(() => {
  const city = String(document.documentElement.dataset.city || "");
  if (city === lastCity) return;
  lastCity = city;
  delete document.documentElement.dataset.filterFailOpen;
  resetContextualUrlState();
  queueVisibilityRepair(350);
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

window.addEventListener("popstate", () => queueVisibilityRepair(0));
window.addEventListener("vivamos:core-ready", () => queueVisibilityRepair(0));