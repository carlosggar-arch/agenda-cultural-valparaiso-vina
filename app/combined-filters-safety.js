const FILTER_PARAMS = ["when", "area", "access", "format", "aud", "cat", "q", "from", "to", "price"];

let lastCity = String(document.documentElement.dataset.city || "");
let repairQueued = false;

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
  repairQueued = false;
  if (!currentFilterStateIsNeutral()) return;

  const grid = document.querySelector('[data-dated-grid]');
  if (!grid) return;
  const directCards = [...grid.querySelectorAll('.event-card[data-event-id]')];
  const groupedCards = [...grid.querySelectorAll('.event-card[data-event-group]')];
  if (!directCards.length || !groupedCards.some((card) => !card.hidden)) return;
  if (directCards.some((card) => !card.hidden)) return;

  // The combined-filter layer owns only a secondary copy of the city dataset.
  // If that fetch fails, it must never hide the already-rendered base agenda and
  // leave only grouped exhibition cards visible. Neutral filtering therefore
  // fails open to the base renderer, which already loaded and validated the data.
  for (const card of directCards) card.hidden = false;
  const section = document.querySelector('[data-dated-section]');
  if (section) section.hidden = false;

  document.documentElement.dataset.filterFailOpen = "true";
  window.dispatchEvent(new CustomEvent("vivamos:filter-fail-open", {
    detail: { city: document.documentElement.dataset.city || "", restored: directCards.length },
  }));
}

function queueVisibilityRepair() {
  if (repairQueued) return;
  repairQueued = true;
  requestAnimationFrame(repairNeutralAgendaVisibility);
}

new MutationObserver(() => {
  const city = String(document.documentElement.dataset.city || "");
  if (city !== lastCity) {
    lastCity = city;
    delete document.documentElement.dataset.filterFailOpen;
    resetContextualUrlState();
  }
  queueVisibilityRepair();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

for (const grid of document.querySelectorAll('[data-dated-grid], [data-program-grid], [data-flexible-grid]')) {
  new MutationObserver(queueVisibilityRepair).observe(grid, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["hidden"],
  });
}

window.addEventListener("popstate", queueVisibilityRepair);
window.addEventListener("vivamos:core-ready", queueVisibilityRepair);
queueVisibilityRepair();
setTimeout(queueVisibilityRepair, 500);
