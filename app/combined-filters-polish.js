const STYLE_ID = "combined-filters-runtime-polish";

if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .legacy-filter-hooks { display: none !important; }
    .hero .smart-search input { padding-left: 2.75rem !important; }
    .filter-workbench { margin-top: 0 !important; }
    .event-card[hidden] { display: none !important; }
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

function hasCombinedFilterState() {
  const params = new URLSearchParams(window.location.search);
  return ["when", "area", "cat", "q", "from", "to"].some((key) => params.has(key));
}

let resyncQueued = false;
function queueFilterResync() {
  if (!hasCombinedFilterState() || resyncQueued) return;
  resyncQueued = true;
  requestAnimationFrame(() => {
    resyncQueued = false;
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
}

for (const grid of document.querySelectorAll("[data-dated-grid], [data-program-grid], [data-flexible-grid]")) {
  new MutationObserver(queueFilterResync).observe(grid, { childList: true });
}

removeNonActionableFilterCopy();
removePriceFilter();
clearRemovedFilterState();
preserveScrollDuringLegacyClick(document.querySelector("[data-section-filters]"));
preserveScrollDuringLegacyClick(document.querySelector("[data-category-filters]"));

requestAnimationFrame(() => window.scrollTo({ top: 0, left: 0, behavior: "auto" }));