import { BRAND_TAGLINE } from "./vivamos-brand.js";

const CITY_LABELS = {
  valparaiso: "Valparaíso / Viña del Mar",
  gijon: "Gijón / Xixón",
};

const TAGLINE = BRAND_TAGLINE;
const HEADER_STYLESHEET = "./header-redesign.css?v=20260817-brandicon1";
const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
const mobileHeaderQuery = window.matchMedia?.("(max-width: 700px)");

function isInstalledApp() {
  return Boolean(standaloneQuery?.matches || window.navigator.standalone === true);
}

function useDirectMobileActions() {
  return Boolean(isInstalledApp() || mobileHeaderQuery?.matches);
}

function viewportWidth() {
  return Number(window.innerWidth || document.documentElement.clientWidth || 9999);
}

function ensureInstalledAppActionStyles() {
  let style = document.querySelector("[data-installed-app-action-styles]");
  if (style) return style;
  style = document.createElement("style");
  style.dataset.installedAppActionStyles = "true";
  style.textContent = `
    html[data-installed-app-actions="below-mosaic"] .filter-workbench::before {
      margin-bottom: .08rem !important;
    }
    html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions {
      grid-column: 1 / -1 !important;
      display: grid !important;
      grid-template-columns: repeat(auto-fit, minmax(52px, 1fr)) !important;
      align-items: stretch !important;
      justify-content: stretch !important;
      width: 100% !important;
      max-width: none !important;
      margin: 0 0 .08rem !important;
      padding: 0 !important;
      gap: .20rem !important;
      overflow: visible !important;
    }
    html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions > * {
      box-sizing: border-box !important;
      width: 100% !important;
      min-width: 0 !important;
      min-height: 44px !important;
      margin: 0 !important;
      padding: .16rem .14rem !important;
      border-radius: 10px !important;
      font-size: .59rem !important;
      line-height: 1.04 !important;
      white-space: normal !important;
      text-align: center !important;
      justify-content: center !important;
      align-items: center !important;
    }
    html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .header-search-toggle {
      display: grid !important;
      place-items: center !important;
    }
    html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .city-switch {
      display: flex !important;
    }
    html[data-installed-app-actions="below-mosaic"] .contribute-source-button {
      display: flex !important;
      flex-direction: column !important;
      gap: .08rem !important;
      color: var(--header-ink, #153f3a) !important;
      background: rgba(255,255,255,.84) !important;
      border: 1px solid rgba(23,79,70,.20) !important;
      text-decoration: none !important;
      font-weight: 780 !important;
      box-shadow: none !important;
    }
    html[data-installed-app-actions="below-mosaic"] .contribute-source-button:hover,
    html[data-installed-app-actions="below-mosaic"] .contribute-source-button:focus-visible {
      border-color: var(--header-control, #174f46) !important;
      color: var(--header-control, #174f46) !important;
      background: #fff !important;
    }
    html[data-installed-app-actions="below-mosaic"] .contribute-source-icon {
      display: block;
      font-size: 1.02rem;
      line-height: .9;
      font-weight: 800;
    }
    @media (max-width: 430px) {
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions {
        gap: .16rem !important;
        grid-template-columns: repeat(auto-fit, minmax(48px, 1fr)) !important;
      }
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions > * {
        min-height: 42px !important;
        padding: .12rem .10rem !important;
        font-size: .55rem !important;
      }
    }
  `;
  document.head.append(style);
  return style;
}

function ensureContributionButton(actions) {
  if (!actions) return null;
  let button = actions.querySelector("[data-contribute-source]");
  if (button) return button;
  button = document.createElement("a");
  button.className = "contribute-source-button";
  button.dataset.contributeSource = "true";
  button.href = "./proponer-fuente.html";
  button.setAttribute("aria-label", "Aportar una fuente cultural");
  button.innerHTML = '<span class="contribute-source-icon" aria-hidden="true">＋</span><span>Aportar fuente</span>';
  actions.append(button);
  return button;
}

function removeContributionButton(actions) {
  actions?.querySelector("[data-contribute-source]")?.remove();
}

function applyApprovedHeaderLayout() {
  const width = viewportWidth();
  const icon = document.querySelector(".brand img");
  const actions = document.querySelector(".header-actions");
  const bottom = document.querySelector(".header-bottom");
  const workbench = document.querySelector(".filter-workbench");

  if (icon) {
    const size = width <= 430 ? 64 : width <= 700 ? 72 : 104;
    icon.style.setProperty("width", `${size}px`, "important");
    icon.style.setProperty("height", `${size}px`, "important");
    icon.dataset.brandIconSize = String(size);
  }

  if (!actions) return;

  if (isInstalledApp() && workbench) {
    ensureInstalledAppActionStyles();
    ensureContributionButton(actions);
    document.documentElement.dataset.installedAppActions = "below-mosaic";
    if (actions.parentElement !== workbench || actions !== workbench.firstElementChild) {
      workbench.insertBefore(actions, workbench.firstElementChild);
    }
    if (bottom) bottom.hidden = true;
    return;
  }

  delete document.documentElement.dataset.installedAppActions;
  removeContributionButton(actions);

  if (useDirectMobileActions()) {
    const header = document.querySelector(".app-header");
    if (header && bottom && actions.parentElement !== header) header.insertBefore(actions, bottom);
    actions.style.setProperty("position", "relative", "important");
    actions.style.setProperty("inset", "auto", "important");
    actions.style.setProperty("display", "flex", "important");
    actions.style.setProperty("justify-content", "flex-end", "important");
    actions.style.setProperty("align-items", "center", "important");
    actions.style.setProperty("width", "100%", "important");
    actions.style.setProperty("max-width", "100%", "important");
    actions.style.setProperty("margin", ".62rem 0 0 auto", "important");
    actions.style.setProperty("padding", "0", "important");
    actions.style.setProperty("gap", width <= 430 ? ".28rem" : ".38rem", "important");
    actions.style.setProperty("flex-wrap", "nowrap", "important");
    if (bottom) bottom.hidden = true;
  } else {
    if (bottom) {
      bottom.hidden = false;
      if (actions.parentElement !== bottom) bottom.append(actions);
      bottom.style.setProperty("position", "absolute", "important");
      bottom.style.setProperty("top", ".55rem", "important");
      bottom.style.setProperty("right", "max(1rem, calc((100vw - 1120px) / 2))", "important");
      bottom.style.setProperty("left", "auto", "important");
      bottom.style.setProperty("width", "auto", "important");
      bottom.style.setProperty("margin", "0", "important");
      bottom.style.setProperty("display", "flex", "important");
      bottom.style.setProperty("justify-content", "flex-end", "important");
    }
    actions.style.setProperty("position", "static", "important");
    actions.style.setProperty("display", "flex", "important");
    actions.style.setProperty("justify-content", "flex-end", "important");
    actions.style.setProperty("align-items", "center", "important");
    actions.style.setProperty("width", "auto", "important");
    actions.style.setProperty("margin", "0", "important");
    actions.style.setProperty("padding", "0", "important");
    actions.style.setProperty("gap", ".45rem", "important");
    actions.style.setProperty("flex-wrap", "nowrap", "important");
  }
}

function ensureHeaderStylesheet() {
  const links = [...document.querySelectorAll('link[href*="header-redesign.css"]')];
  if (links.length) {
    for (const extra of links.slice(1)) extra.remove();
    return;
  }
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = HEADER_STYLESHEET;
  document.head.append(link);
}

function closeSearch() {
  const popover = document.querySelector("[data-header-search-popover]");
  const toggle = document.querySelector("[data-header-search-toggle]");
  if (!popover || !toggle || popover.hidden) return;
  popover.hidden = true;
  toggle.setAttribute("aria-expanded", "false");
}

function toggleSearch() {
  const popover = document.querySelector("[data-header-search-popover]");
  const toggle = document.querySelector("[data-header-search-toggle]");
  const input = document.querySelector("[data-search]");
  if (!popover || !toggle) return;
  const opening = popover.hidden;
  popover.hidden = !opening;
  toggle.setAttribute("aria-expanded", opening ? "true" : "false");
  if (opening) requestAnimationFrame(() => input?.focus());
}

function bindSearchToggle(toggle) {
  if (!toggle || toggle.dataset.headerSearchBound === "true") return;
  toggle.dataset.headerSearchBound = "true";
  toggle.addEventListener("click", toggleSearch);
}

function buildHeaderStructure() {
  const header = document.querySelector(".app-header");
  const brandCopy = document.querySelector(".brand span");
  const searchRow = document.querySelector("[data-search-row]");
  const actions = document.querySelector(".header-actions");
  if (!header || !brandCopy) return;

  let kicker = brandCopy.querySelector(".header-kicker");
  if (!kicker) {
    kicker = document.createElement("span");
    kicker.className = "header-kicker";
    kicker.textContent = "Agenda cultural";
    brandCopy.append(kicker);
  }

  let cityTitle = brandCopy.querySelector("[data-header-city-title]");
  if (!cityTitle) {
    cityTitle = document.createElement("span");
    cityTitle.className = "header-city-title";
    cityTitle.dataset.headerCityTitle = "";
    brandCopy.append(kicker);
  }

  let tagline = brandCopy.querySelector(".header-tagline");
  if (!tagline) {
    tagline = document.createElement("span");
    tagline.className = "header-tagline";
    tagline.textContent = TAGLINE;
    brandCopy.append(tagline);
  }

  let bottom = header.querySelector(".header-bottom");
  if (!bottom) {
    bottom = document.createElement("div");
    bottom.className = "header-bottom";
    header.append(bottom);
  }

  if (actions && !isInstalledApp()) {
    if (mobileHeaderQuery?.matches) {
      if (actions.parentElement !== header || actions.nextElementSibling !== bottom) header.insertBefore(actions, bottom);
      bottom.hidden = true;
    } else {
      bottom.hidden = false;
      if (actions.parentElement !== bottom) bottom.append(actions);
    }
  }

  if (actions && !actions.querySelector("[data-header-search-toggle]")) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "header-search-toggle";
    toggle.dataset.headerSearchToggle = "";
    toggle.setAttribute("aria-label", "Buscar actividades");
    toggle.setAttribute("aria-expanded", "false");
    toggle.innerHTML = '<span aria-hidden="true">⌕</span>';
    actions.prepend(toggle);
  }
  bindSearchToggle(actions?.querySelector("[data-header-search-toggle]"));

  let searchPopover = header.querySelector("[data-header-search-popover]");
  if (!searchPopover) {
    searchPopover = document.createElement("div");
    searchPopover.className = "header-search-popover";
    searchPopover.dataset.headerSearchPopover = "";
    searchPopover.hidden = true;
    header.append(searchPopover);
  }
  if (searchRow && searchRow.parentElement !== searchPopover) searchPopover.append(searchRow);

  let art = header.querySelector(".header-art");
  if (!art) {
    art = document.createElement("div");
    art.className = "header-art";
    art.setAttribute("aria-hidden", "true");
    header.append(art);
  }

  header.dataset.headerRedesign = "hero-v6-installed-actions-below-mosaic";
  applyApprovedHeaderLayout();
}

function applyHeaderIdentity() {
  buildHeaderStructure();
  applyApprovedHeaderLayout();
  const city = document.documentElement.dataset.city || "valparaiso";
  const label = CITY_LABELS[city] || CITY_LABELS.valparaiso;
  const cityTitle = document.querySelector("[data-header-city-title]");
  const subtitle = document.querySelector("[data-city-subtitle]");

  if (cityTitle) cityTitle.textContent = label;
  if (subtitle) subtitle.textContent = label;
}

ensureHeaderStylesheet();
applyHeaderIdentity();

new MutationObserver(applyHeaderIdentity).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-city"],
});

window.addEventListener("resize", applyHeaderIdentity);
window.addEventListener("orientationchange", applyHeaderIdentity);
standaloneQuery?.addEventListener?.("change", applyHeaderIdentity);
mobileHeaderQuery?.addEventListener?.("change", applyHeaderIdentity);

document.addEventListener("pointerdown", (event) => {
  const popover = document.querySelector("[data-header-search-popover]");
  const toggle = document.querySelector("[data-header-search-toggle]");
  if (!popover || popover.hidden) return;
  if (popover.contains(event.target) || toggle?.contains(event.target)) return;
  closeSearch();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeSearch();
});

export { TAGLINE, applyHeaderIdentity };
