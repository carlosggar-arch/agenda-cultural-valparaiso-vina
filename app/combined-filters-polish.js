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

function preserveScrollDuringLegacyClick(container) {
  container?.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const top = window.scrollY;
    requestAnimationFrame(() => window.scrollTo({ top, left: 0, behavior: "auto" }));
  }, true);
}

preserveScrollDuringLegacyClick(document.querySelector("[data-section-filters]"));
preserveScrollDuringLegacyClick(document.querySelector("[data-category-filters]"));

requestAnimationFrame(() => window.scrollTo({ top: 0, left: 0, behavior: "auto" }));
