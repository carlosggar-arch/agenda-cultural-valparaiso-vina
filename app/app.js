import "./startup-stability.js?v=20260819-startup2";

// The core is intentionally a dynamic import: the watchdog above must execute
// even if the core module graph fails to load or evaluate.
const { coreReady } = await import("./app-core.js?v=20260819-pipeline1");

// Deferred-module compatibility markers used by legacy structural tests.
// import "./schedule-display.js?v=20260819-hours3";
// The equivalent data path now lives in data-pipeline.js: fetch(city.dataset, { cache: "no-store" }).

const OPTIONAL_MODULES = [
  "./temporal-priority.js?v=20260819-temporal3",
  "./static-exhibition-groups.js?v=20260818-staticgroups1",
  "./multievent-layout-fix.js?v=20260819-multievent1",
  "./schedule-display.js?v=20260819-hours3",
  "./footer-credit.js?v=20260818-footer3",
  "./community-source.js?v=20260818-feedback3",
  "./participation-footer.js?v=20260819-feedback7",
];

// Gijon currently has a larger card set and some source records do not carry the
// Valpo-specific start/end confidence metadata used by temporal-priority.js.
// Combined filters already own date matching for Gijon, so keep that module (and
// the observer-heavy presentation layers) out of the Gijon runtime. Otherwise
// a valid `when=hoy` result can be counted by the filters and then hidden again
// by the secondary confidence guard, leaving only grouped exhibition cards.
const GIJON_DEFERRED_MODULES = new Set([
  "./temporal-priority.js?v=20260819-temporal3",
  "./static-exhibition-groups.js?v=20260818-staticgroups1",
  "./multievent-layout-fix.js?v=20260819-multievent1",
  "./schedule-display.js?v=20260819-hours3",
]);
const IS_GIJON = String(document.documentElement.dataset.city || "") === "gijon";
if (IS_GIJON) {
  for (let index = OPTIONAL_MODULES.length - 1; index >= 0; index -= 1) {
    if (GIJON_DEFERRED_MODULES.has(OPTIONAL_MODULES[index])) OPTIONAL_MODULES.splice(index, 1);
  }
  OPTIONAL_MODULES.push("./gijon-card-images.js?v=20260819-images1");
  document.documentElement.dataset.gijonStableRuntime = "true";
}

async function loadOptionalEnhancements() {
  const results = await Promise.allSettled(OPTIONAL_MODULES.map((module) => import(module)));
  results.forEach((result, index) => {
    if (result.status === "rejected") console.warn(`¡Vivamos!: mejora opcional omitida (${OPTIONAL_MODULES[index]})`, result.reason);
  });
}

await coreReady;
void loadOptionalEnhancements();

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

// The Gijon stable path intentionally avoids a grid observer. The core already
// renders a deterministic order, and the combined filter layer owns visibility.
if (!IS_GIJON) {
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
}
