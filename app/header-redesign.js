import { BRAND_TAGLINE } from "./vivamos-brand.js";

const CITY_LABELS = {
  valparaiso: "Valparaíso / Viña del Mar",
  gijon: "Gijón / Xixón",
};

const TAGLINE = BRAND_TAGLINE;
const HEADER_STYLESHEET = "./header-redesign.css?v=20260817-brandicon1";
const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
const mobileHeaderQuery = window.matchMedia?.("(max-width: 700px)");

function useDirectMobileActions() {
  return Boolean(standaloneQuery?.matches || window.navigator.standalone === true || mobileHeaderQuery?.matches);
}

function ensureHeaderStylesheet() {
  const links = [...document.querySelectorAll('link[href*="header-redesign.css"]')];
  if (links.length) {
    // The shell loads the final stylesheet in <head>. Do not rewrite the href
    // during hydration, because that creates a second CSS request and layout shift.
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
    brandCopy.append(cityTitle);
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

  if (actions) {
    if (useDirectMobileActions()) {
      if (actions.parentElement !== header || actions.nextElementSibling !== bottom) {
        header.insertBefore(actions, bottom);
      }
      bottom.hidden = true;
    } else {
      bottom.hidden = false;
      if (actions.parentElement !== bottom) bottom.append(actions);
    }
  }

  let searchToggle = actions?.querySelector("[data-header-search-toggle]");
  if (actions && !searchToggle) {
    searchToggle = document.createElement("button");
    searchToggle.type = "button";
    searchToggle.className = "header-search-toggle";
    searchToggle.dataset.headerSearchToggle = "";
    searchToggle.setAttribute("aria-label", "Buscar actividades");
    searchToggle.setAttribute("aria-expanded", "false");
    searchToggle.innerHTML = '<span aria-hidden="true">⌕</span>';
    actions.prepend(searchToggle);
  }
  bindSearchToggle(searchToggle);

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

  header.dataset.headerRedesign = "hero-v4-mobile-direct-actions";
}

function applyHeaderIdentity() {
  buildHeaderStructure();
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
