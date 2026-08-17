const STYLE_ID = "combined-filters-runtime-polish";
const REJECTED_EVENT_IDS = new Set([
  "agenda_968c623b60b70d2976410175",
]);

if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .legacy-filter-hooks { display: none !important; }
    .hero .smart-search input { padding-left: 2.75rem !important; }
    .filter-workbench { margin-top: 0 !important; }
    .event-card[hidden] { display: none !important; }
    .event-card[data-event-id="agenda_968c623b60b70d2976410175"] { display: none !important; }
  `;
  document.head.append(style);
}

function removeNonActionableFilterCopy() {
  for (const selector of [
    ".discovery-heading",
    ".filter-workbench-heading",
    ".category-explorer-heading",
    ".filter-help",
  ]) {
    document.querySelector(selector)?.remove();
  }
}

function removePriceFilter() {
  document.querySelector("[data-combined-price]")?.closest(".filter-group")?.remove();
}

function clearRemovedFilterState() {
  const url = new URL(window.location.href);
  let changed = false;
  for (const key of ["price", "access", "format", "aud"]) {
    if (!url.searchParams.has(key)) continue;
    url.searchParams.delete(key);
    changed = true;
  }
  if (!changed) return;
  const next = `${url.pathname}${url.search}${url.hash}`;
  history.replaceState(null, "", next);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function preserveScrollDuringLegacyClick(container) {
  container?.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const top = window.scrollY;
    requestAnimationFrame(() => window.scrollTo({ top, left: 0, behavior: "auto" }));
  }, true);
}

function refreshVisibleTotals() {
  let total = 0;
  for (const [sectionSelector, totalSelector, gridSelector] of [
    ["[data-dated-section]", "[data-dated-total]", "[data-dated-grid]"],
    ["[data-program-section]", "[data-program-total]", "[data-program-grid]"],
    ["[data-flexible-section]", "[data-flexible-total]", "[data-flexible-grid]"],
  ]) {
    const section = document.querySelector(sectionSelector);
    const counter = document.querySelector(totalSelector);
    const grid = document.querySelector(gridSelector);
    const count = grid?.querySelectorAll(".event-card[data-event-id]").length || 0;
    if (counter) counter.textContent = String(count);
    if (section) section.hidden = count === 0;
    total += count;
  }
  const overall = document.querySelector("[data-total]");
  if (overall) overall.textContent = String(total);
}

function shouldRejectEditorialCard(card) {
  const id = card.dataset.eventId || "";
  if (REJECTED_EVENT_IDS.has(id)) return true;
  const text = String(card.textContent || "").toLocaleLowerCase("es");
  const editorialCinemaPost = text.includes("instagram.com")
    && text.includes("sabías que")
    && text.includes("campamento")
    && text.includes("cine dentro del cine");
  return editorialCinemaPost;
}

function removeRejectedEditorialCards() {
  let removed = false;
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    if (!shouldRejectEditorialCard(card)) continue;
    card.remove();
    removed = true;
  }
  if (removed) refreshVisibleTotals();
}

function hasCombinedFilterState() {
  const params = new URLSearchParams(window.location.search);
  return ["when", "area", "cat", "q", "from", "to"].some((key) => params.has(key));
}

let resyncQueued = false;
function queueFilterResync() {
  removeRejectedEditorialCards();
  if (!hasCombinedFilterState() || resyncQueued) return;
  resyncQueued = true;
  requestAnimationFrame(() => {
    resyncQueued = false;
    window.dispatchEvent(new PopStateEvent("popstate"));
    requestAnimationFrame(removeRejectedEditorialCards);
  });
}

for (const grid of document.querySelectorAll("[data-dated-grid], [data-program-grid], [data-flexible-grid]")) {
  new MutationObserver(queueFilterResync).observe(grid, { childList: true });
}

removeNonActionableFilterCopy();
removePriceFilter();
clearRemovedFilterState();
removeRejectedEditorialCards();
preserveScrollDuringLegacyClick(document.querySelector("[data-section-filters]"));
preserveScrollDuringLegacyClick(document.querySelector("[data-category-filters]"));

requestAnimationFrame(() => window.scrollTo({ top: 0, left: 0, behavior: "auto" }));