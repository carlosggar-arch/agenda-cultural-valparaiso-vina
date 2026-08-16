const CITY_LABELS = {
  valparaiso: "Valparaíso / Viña del Mar",
  gijon: "Gijón / Xixón",
};

const TAGLINE = "Cultura, panoramas y experiencias para disfrutar cerca de ti.";

function ensureHeaderStylesheet() {
  if (document.querySelector('link[href="./header-redesign.css"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./header-redesign.css";
  document.head.append(link);
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
  if (searchRow && searchRow.parentElement !== bottom) bottom.append(searchRow);
  if (actions && actions.parentElement !== bottom) bottom.append(actions);

  let art = header.querySelector(".header-art");
  if (!art) {
    art = document.createElement("div");
    art.className = "header-art";
    art.setAttribute("aria-hidden", "true");
    header.append(art);
  }

  header.dataset.headerRedesign = "hero-v2";
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

export { TAGLINE, applyHeaderIdentity };
