import { BRAND_TAGLINE } from "./vivamos-brand.js";

const CITY_LABELS = {
  valparaiso: "Valparaíso / Viña del Mar",
  gijon: "Gijón / Xixón",
};

const TAGLINE = BRAND_TAGLINE;

function ensureHeaderStylesheet() {
  if (document.querySelector('link[href="./header-redesign.css"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./header-redesign.css";
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
  if (actions && actions.parentElement !== bottom) bottom.append(actions);

  if (actions && !actions.querySelector("[data-header-search-toggle]")) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "header-search-toggle";
    toggle.dataset.headerSearchToggle = "";
    toggle.setAttribute("aria-label", "Buscar actividades");
    toggle.setAttribute("aria-expanded", "false");
    toggle.innerHTML = '<span aria-hidden="true">⌕</span>';
    actions.prepend(toggle);
    toggle.addEventListener("click", toggleSearch);
  }

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

  header.dataset.headerRedesign = "hero-v3";
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
