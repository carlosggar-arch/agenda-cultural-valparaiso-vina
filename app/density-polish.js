const STYLE_ID = "vivamos-density-polish";

function ensureDensityStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    /* The illustration shares the hero with the copy instead of reserving
       a separate visual block. This keeps the identity while reducing height. */
    .app-header {
      min-height: 158px !important;
      padding-top: 1rem !important;
      padding-bottom: .78rem !important;
    }
    .app-header .brand {
      width: min(840px, 78vw) !important;
    }
    .app-header .brand img {
      width: 58px !important;
      height: 58px !important;
    }
    .app-header .brand strong {
      font-size: 1.32rem !important;
      margin-bottom: .28rem !important;
    }
    .app-header .header-kicker {
      margin-bottom: .18rem !important;
    }
    .app-header .header-city-title {
      font-size: clamp(1.55rem, 3.35vw, 3rem) !important;
    }
    .app-header .header-tagline {
      max-width: none !important;
      margin-top: .34rem !important;
      white-space: nowrap !important;
      font-size: clamp(.82rem, 1.35vw, .95rem) !important;
      line-height: 1.2 !important;
    }
    .app-header .header-art {
      top: 0 !important;
      bottom: auto !important;
      width: 62% !important;
      height: 100% !important;
      opacity: .7 !important;
      background-size: cover !important;
      -webkit-mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.18) 16%, #000 46%, #000 100%) !important;
      mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.18) 16%, #000 46%, #000 100%) !important;
    }

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

    /* Zero-result choices add noise. Both category chips and contextual quick
       filters are hidden, regardless of display rules from older visual layers. */
    .category-filters [data-category-filter][hidden],
    .quick-sections [data-section-filter][hidden] {
      display: none !important;
    }

    @media (max-width: 700px) {
      .app-header {
        min-height: 168px !important;
        padding: .78rem .8rem .72rem !important;
      }
      .app-header .brand {
        width: 100% !important;
        gap: .5rem !important;
      }
      .app-header .brand img {
        width: 44px !important;
        height: 44px !important;
      }
      .app-header .brand strong {
        font-size: 1.02rem !important;
        margin-bottom: .2rem !important;
      }
      .app-header .header-kicker {
        font-size: .52rem !important;
      }
      .app-header .header-city-title {
        margin-top: .3rem !important;
        font-size: clamp(1.08rem, 5.25vw, 1.75rem) !important;
      }
      .app-header .header-tagline {
        max-width: none !important;
        white-space: nowrap !important;
        font-size: clamp(.68rem, 2.7vw, .8rem) !important;
        margin-top: .28rem !important;
      }
      .app-header .header-art {
        top: 0 !important;
        bottom: auto !important;
        width: 78% !important;
        height: 100% !important;
        opacity: .32 !important;
        -webkit-mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.14) 18%, #000 52%, #000 100%) !important;
        mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.14) 18%, #000 52%, #000 100%) !important;
      }
      .app-header .header-bottom {
        top: .58rem !important;
        right: .58rem !important;
      }
      .app-header .header-actions {
        gap: .3rem !important;
      }
      .app-header .header-search-toggle,
      .app-header .install-button,
      .app-header .city-switch {
        width: 37px !important;
        min-width: 37px !important;
        height: 37px !important;
        min-height: 37px !important;
        padding: 0 !important;
        display: inline-grid !important;
        place-items: center !important;
      }
      .app-header .install-button > span:last-child,
      .app-header .city-switch [data-city-switch-label],
      .app-header .city-switch > span:last-child {
        display: none !important;
      }
    }
  `;
  document.head.append(style);
}

function numericCount(button, selector) {
  const value = Number.parseInt(button.querySelector(selector)?.textContent || "", 10);
  return Number.isFinite(value) ? value : null;
}

function enforceCategoryVisibility() {
  const container = document.querySelector("[data-category-filters]");
  if (!container) return;

  for (const button of container.querySelectorAll("[data-category-filter]")) {
    const id = button.dataset.categoryFilter || "";
    if (!id) {
      if (!button.hidden) button.hidden = true;
      continue;
    }
    const count = numericCount(button, "small");
    if (count === null) continue;
    const shouldHide = count === 0;
    if (button.hidden !== shouldHide) button.hidden = shouldHide;
  }
}

function enforceQuickFilterVisibility() {
  const container = document.querySelector("[data-section-filters]");
  if (!container) return;

  let hiddenActive = false;
  for (const button of container.querySelectorAll("[data-section-filter]")) {
    const id = button.dataset.sectionFilter || "";
    const count = numericCount(button, "[data-section-count]");
    if (!id || count === null) continue;
    const shouldHide = id !== "todos" && count === 0;
    if (button.hidden !== shouldHide) button.hidden = shouldHide;
    if (shouldHide && (button.classList.contains("active") || button.getAttribute("aria-pressed") === "true")) {
      hiddenActive = true;
    }
  }

  if (hiddenActive) {
    const fallback = container.querySelector('[data-section-filter="todos"]');
    if (fallback && !fallback.hidden) queueMicrotask(() => fallback.click());
  }
}

function enforceDensity() {
  enforceCategoryVisibility();
  enforceQuickFilterVisibility();
}

ensureDensityStyles();
enforceDensity();

const categoryContainer = document.querySelector("[data-category-filters]");
if (categoryContainer) {
  new MutationObserver(enforceCategoryVisibility).observe(categoryContainer, {
    childList: true,
    subtree: true,
    characterData: true,
  });
}

const sectionContainer = document.querySelector("[data-section-filters]");
if (sectionContainer) {
  new MutationObserver(enforceQuickFilterVisibility).observe(sectionContainer, {
    childList: true,
    subtree: true,
    characterData: true,
  });
}

export { enforceCategoryVisibility, enforceQuickFilterVisibility };
