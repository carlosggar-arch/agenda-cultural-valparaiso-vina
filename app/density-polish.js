const STYLE_ID = "vivamos-density-polish";

function ensureDensityStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    /* Header actions are utilities, not a second content row. */
    .app-header .header-bottom {
      position: absolute !important;
      top: 1rem !important;
      right: max(1rem, calc((100vw - 1120px) / 2)) !important;
      left: auto !important;
      width: auto !important;
      margin: 0 !important;
      z-index: 20 !important;
    }
    .app-header .header-actions {
      justify-content: flex-end !important;
      flex-wrap: nowrap !important;
    }

    /* Hidden contextual categories must stay hidden even if another visual
       layer assigns a display mode to category chips. */
    .category-filters [data-category-filter][hidden] {
      display: none !important;
    }

    @media (max-width: 700px) {
      .app-header .header-bottom {
        top: .72rem !important;
        right: .72rem !important;
      }
      .app-header .header-actions {
        gap: .34rem !important;
      }
      .app-header .header-search-toggle,
      .app-header .install-button,
      .app-header .city-switch {
        width: 39px !important;
        min-width: 39px !important;
        height: 39px !important;
        min-height: 39px !important;
        padding: 0 !important;
        display: inline-grid !important;
        place-items: center !important;
      }
      .app-header .install-button > span:last-child,
      .app-header .city-switch [data-city-switch-label],
      .app-header .city-switch > span:last-child {
        display: none !important;
      }
      .app-header .header-city-title {
        margin-top: .55rem !important;
      }
    }
  `;
  document.head.append(style);
}

function categoryCount(button) {
  const value = Number.parseInt(button.querySelector("small")?.textContent || "", 10);
  return Number.isFinite(value) ? value : null;
}

function enforceCategoryVisibility() {
  const container = document.querySelector("[data-category-filters]");
  if (!container) return;

  for (const button of container.querySelectorAll("[data-category-filter]")) {
    const id = button.dataset.categoryFilter || "";
    if (!id) {
      button.hidden = true;
      continue;
    }
    const count = categoryCount(button);
    if (count === null) continue;
    button.hidden = count === 0;
  }
}

ensureDensityStyles();
enforceCategoryVisibility();

const categoryContainer = document.querySelector("[data-category-filters]");
if (categoryContainer) {
  new MutationObserver(enforceCategoryVisibility).observe(categoryContainer, {
    childList: true,
    subtree: true,
    characterData: true,
  });
}

export { enforceCategoryVisibility };
