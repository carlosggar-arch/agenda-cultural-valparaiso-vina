const STYLE_ID = "combined-filters-runtime-polish";

if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .legacy-filter-hooks { display: none !important; }
    .discovery-heading { display: flex !important; }
    .category-filter-panel .category-explorer-heading { display: flex !important; }
    .agenda-heading { display: flex !important; margin-bottom: .9rem !important; }
    .hero .smart-search input { padding-left: 2.75rem !important; }
    .filter-workbench { margin-top: .2rem !important; }
    .event-card[hidden] { display: none !important; }
    @media (max-width: 800px) {
      .discovery-heading,
      .agenda-heading,
      .category-filter-panel .category-explorer-heading {
        align-items: flex-start !important;
        flex-direction: column !important;
      }
    }
  `;
  document.head.append(style);
}

function clearLegacyPriceState() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("price")) return;
  url.searchParams.delete("price");
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

/*
  Do not observe event-grid childList mutations here. Search relevance ordering
  intentionally moves existing cards inside their grids; a grid observer would
  turn those moves into a popstate/resync loop. combined-filters.js already
  resynchronizes when the city or discovery state changes.
*/
clearLegacyPriceState();
preserveScrollDuringLegacyClick(document.querySelector("[data-section-filters]"));
preserveScrollDuringLegacyClick(document.querySelector("[data-category-filters]"));

requestAnimationFrame(() => window.scrollTo({ top: 0, left: 0, behavior: "auto" }));