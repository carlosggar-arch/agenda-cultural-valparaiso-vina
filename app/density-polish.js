const STYLE_ID = "vivamos-density-polish";

function ensureDensityStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    /* Keep the typography legible and let the copy determine the hero height.
       The visual compaction comes from cropping the illustration around the
       horizon/monument instead of shrinking the brand text. */
    .app-header {
      min-height: 0 !important;
      padding-top: .85rem !important;
      padding-bottom: .6rem !important;
    }
    .app-header .brand {
      width: min(840px, 78vw) !important;
      align-items: flex-start !important;
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
      line-height: .98 !important;
    }
    .app-header .header-tagline {
      max-width: none !important;
      margin-top: .34rem !important;
      margin-bottom: 0 !important;
      white-space: nowrap !important;
      font-size: clamp(.82rem, 1.35vw, .95rem) !important;
      line-height: 1.2 !important;
    }
    .app-header .header-art {
      top: 0 !important;
      bottom: auto !important;
      width: 55% !important;
      height: 100% !important;
      opacity: .68 !important;
      background-size: cover !important;
      /* In a shallow desktop hero, `bottom` crops the 900x360 SVG down to
         almost only its lower sea band. Centering around 58% keeps the
         Elogio/horizon and only a narrow amount of sea visible. */
      background-position: right 58% !important;
      -webkit-mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.16) 18%, #000 48%, #000 100%) !important;
      mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.16) 18%, #000 48%, #000 100%) !important;
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
        min-height: 0 !important;
        padding: .72rem .78rem .58rem !important;
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
        margin-bottom: .1rem !important;
      }
      .app-header .header-city-title {
        margin-top: .2rem !important;
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
        width: 72% !important;
        height: 100% !important;
        opacity: .3 !important;
        background-position: 58% center !important;
        -webkit-mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.13) 20%, #000 55%, #000 100%) !important;
        mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.13) 20%, #000 55%, #000 100%) !important;
      }
      .app-header .header-bottom {
        top: .54rem !important;
        right: .54rem !important;
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
