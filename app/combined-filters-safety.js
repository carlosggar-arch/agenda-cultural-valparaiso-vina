const FILTER_PARAMS = ["when", "area", "access", "format", "aud", "cat", "q", "from", "to", "price"];

let lastCity = String(document.documentElement.dataset.city || "");
let repairTimer = null;

function currentFilterStateIsNeutral() {
  const params = new URLSearchParams(window.location.search);
  for (const key of FILTER_PARAMS) {
    const value = String(params.get(key) || "").trim();
    if (!value) continue;
    if (["when", "area", "access", "format", "aud"].includes(key) && value === "todos") continue;
    return false;
  }
  return document.querySelectorAll('[data-combined-category-filters] [data-combined-category].active').length === 0
    && !String(document.querySelector('[data-smart-search]')?.value || "").trim()
    && !String(document.querySelector('[data-date-from]')?.value || "").trim()
    && !String(document.querySelector('[data-date-to]')?.value || "").trim();
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

  // The combined-filter layer owns only a secondary copy of the city dataset.
  // If that fetch fails, it must never hide the already-rendered base agenda.
  // Neutral filtering therefore fails open to the base renderer, which already
  // loaded and validated the city data. Exhibition sentinels are restored too
  // so grouped exhibition cards stay consistent with the recovered base agenda.
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

// combined-filters-safety.js is imported only after the main combined-filter
// module has finished its initial applyFilters(). One immediate check is enough
// for first load; bounded retries cover the asynchronous base renderer without
// adding a grid MutationObserver that could participate in rendering feedback.
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
