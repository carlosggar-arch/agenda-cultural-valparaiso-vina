const STYLE_ID = "vivamos-density-polish";

function ensureDensityStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    /* Keep the city illustration, but let content determine the hero height.
       The previous minimum height left a visibly empty band below the tagline. */
    .app-header {
      min-height: 124px !important;
      padding-top: .72rem !important;
      padding-bottom: .5rem !important;
    }
    .app-header .brand {
      width: min(760px, 70vw) !important;
      align-items: flex-start !important;
    }
    .app-header .brand img {
      width: 52px !important;
      height: 52px !important;
    }
    .app-header .brand strong {
      font-size: 1.18rem !important;
      margin-bottom: .18rem !important;
    }
    .app-header .header-kicker {
      margin-bottom: .08rem !important;
    }
    .app-header .header-city-title {
      font-size: clamp(1.48rem, 3vw, 2.65rem) !important;
      line-height: .95 !important;
    }
    .app-header .header-tagline {
      max-width: none !important;
      margin-top: .24rem !important;
      margin-bottom: 0 !important;
      white-space: nowrap !important;
      font-size: clamp(.78rem, 1.2vw, .9rem) !important;
      line-height: 1.12 !important;
    }
    .app-header .header-art {
      top: 0 !important;
      bottom: auto !important;
      width: 55% !important;
      height: 100% !important;
      opacity: .62 !important;
      background-size: cover !important;
      background-position: center bottom !important;
      -webkit-mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.15) 18%, #000 48%, #000 100%) !important;
      mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.15) 18%, #000 48%, #000 100%) !important;
    }

    /* Header actions are utilities, not a second content row. */
    .app-header .header-bottom {
      position: absolute !important;
      top: .72rem !important;
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
        min-height: 132px !important;
        padding: .58rem .68rem .46rem !important;
      }
      .app-header .brand {
        width: 100% !important;
        gap: .42rem !important;
      }
      .app-header .brand img {
        width: 40px !important;
        height: 40px !important;
      }
      .app-header .brand strong {
        font-size: .96rem !important;
        margin-bottom: .12rem !important;
      }
      .app-header .header-kicker {
        font-size: .48rem !important;
        margin-bottom: .04rem !important;
      }
      .app-header .header-city-title {
        margin-top: .18rem !important;
        font-size: clamp(1.02rem, 5vw, 1.58rem) !important;
      }
      .app-header .header-tagline {
        max-width: none !important;
        white-space: nowrap !important;
        font-size: clamp(.64rem, 2.55vw, .76rem) !important;
        margin-top: .2rem !important;
      }
      .app-header .header-art {
        top: 0 !important;
        bottom: auto !important;
        width: 70% !important;
        height: 100% !important;
        opacity: .26 !important;
        background-position: 58% bottom !important;
        -webkit-mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.11) 20%, #000 55%, #000 100%) !important;
        mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.11) 20%, #000 55%, #000 100%) !important;
      }
      .app-header .header-bottom {
        top: .46rem !important;
        right: .46rem !important;
      }
      .app-header .header-actions {
        gap: .26rem !important;
      }
      .app-header .header-search-toggle,
      .app-header .install-button,
      .app-header .city-switch {
        width: 35px !important;
        min-width: 35px !important;
        height: 35px !important;
        min-height: 35px !important;
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

    @media (max-width: 560px) {
      /* Three compact category choices per row substantially reduce vertical
         scrolling in the installed app while preserving all non-empty choices. */
      .category-filters {
        grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
        gap: .32rem !important;
      }
      .category-chip {
        padding: .4rem .42rem !important;
        gap: .26rem !important;
        font-size: .7rem !important;
        line-height: 1.05 !important;
      }
      .category-chip small {
        font-size: .6rem !important;
        min-width: 1.05rem !important;
        padding: .06rem .2rem !important;
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
