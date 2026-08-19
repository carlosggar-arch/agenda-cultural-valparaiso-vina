import "./startup-stability.js?v=20260819-startup1";
import "./event-data-corrections.js?v=20260819-rioja1";
import "./category-normalizer.js?v=20260819-categories4";
import "./title-normalizer-bootstrap.js?v=20260818-title3";
import "./session-occurrence-normalizer.js?v=20260819-sessions1";
import "./program-visibility-policy.js?v=20260819-programs1";
import "./app-core.js?v=20260818-exhibitions1";
import "./temporal-priority.js?v=20260819-temporal3";
import "./static-exhibition-groups.js?v=20260818-staticgroups1";
import "./multievent-layout-fix.js?v=20260819-multievent1";
import "./schedule-display.js?v=20260819-hours3";
import "./footer-credit.js?v=20260818-footer3";
import "./community-source.js?v=20260818-feedback3";
import "./participation-footer.js?v=20260819-feedback7";

let exhibitionOrderQueued = false;

function defaultFiltersAreNeutral() {
  const when = document.querySelector('[data-combined-when] [data-filter-value].active')?.dataset?.filterValue || "todos";
  const area = document.querySelector('[data-combined-area] [data-filter-value].active')?.dataset?.filterValue || "todos";
  const categories = document.querySelectorAll('[data-combined-category-filters] [data-combined-category].active').length;
  const query = String(document.querySelector('[data-smart-search]')?.value || "").trim();
  const from = String(document.querySelector('[data-date-from]')?.value || "").trim();
  const to = String(document.querySelector('[data-date-to]')?.value || "").trim();
  return when === "todos" && area === "todos" && categories === 0 && !query && !from && !to;
}

function placeExhibitionsLast() {
  exhibitionOrderQueued = false;
  if (!defaultFiltersAreNeutral()) return;
  const grid = document.querySelector('[data-dated-grid]');
  if (!grid) return;
  const cards = [...grid.children].filter((node) => node.classList?.contains("event-card"));
  if (cards.length < 2) return;
  const regular = cards.filter((card) => card.dataset.category !== "exposiciones");
  const exhibitions = cards.filter((card) => card.dataset.category === "exposiciones");
  if (!regular.length || !exhibitions.length) return;
  const ordered = [...regular, ...exhibitions];
  if (ordered.every((card, index) => card === cards[index])) return;
  const fragment = document.createDocumentFragment();
  for (const card of ordered) fragment.append(card);
  grid.append(fragment);
}

function scheduleExhibitionOrder() {
  if (exhibitionOrderQueued) return;
  exhibitionOrderQueued = true;
  queueMicrotask(placeExhibitionsLast);
}

const datedGrid = document.querySelector('[data-dated-grid]');
if (datedGrid) {
  new MutationObserver(scheduleExhibitionOrder).observe(datedGrid, { childList: true });
}
document.addEventListener("click", (event) => {
  if (event.target.closest('[data-filter-value], [data-combined-category], [data-filter-clear]')) scheduleExhibitionOrder();
});
document.addEventListener("input", (event) => {
  if (event.target.matches('[data-smart-search], [data-date-from], [data-date-to]')) scheduleExhibitionOrder();
});
scheduleExhibitionOrder();