const CITY_LABELS = {
  valparaiso: "Valparaíso / Viña del Mar",
  gijon: "Gijón / Xixón",
};

function ensureHeaderStylesheet() {
  if (document.querySelector('link[href="./header-redesign.css"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./header-redesign.css";
  document.head.append(link);
}

function applyHeaderIdentity() {
  const city = document.documentElement.dataset.city || "valparaiso";
  const label = CITY_LABELS[city] || CITY_LABELS.valparaiso;
  const subtitle = document.querySelector("[data-city-subtitle]");
  const heroTitle = document.querySelector("[data-hero-title]");
  const heroCopy = document.querySelector("[data-hero-copy]");

  if (subtitle) subtitle.dataset.headerCity = label;
  if (heroTitle) heroTitle.textContent = "Cultura, panoramas y experiencias para disfrutar cerca de ti.";
  if (heroCopy) heroCopy.textContent = "";
}

ensureHeaderStylesheet();
applyHeaderIdentity();

new MutationObserver(applyHeaderIdentity).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-city"],
});

export { applyHeaderIdentity };
