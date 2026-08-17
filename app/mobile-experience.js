const MOBILE_QUERY = "(max-width: 700px)";
const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
const chooserBackdrop = document.querySelector("[data-chooser-backdrop]");

function isStandalone() {
  return Boolean(standaloneQuery?.matches || window.navigator.standalone === true);
}

function syncStandaloneFlag() {
  document.documentElement.dataset.standalone = String(isStandalone());
}

function createTabButton(action, icon, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.mobileAction = action;
  button.setAttribute("aria-label", label);
  button.innerHTML = `<span class="mobile-tab-icon" aria-hidden="true">${icon}</span><span>${label}</span>`;
  return button;
}

function buildTabbar() {
  let nav = document.querySelector("[data-mobile-tabbar]");
  if (nav) return nav;
  nav = document.createElement("nav");
  nav.className = "mobile-tabbar";
  nav.dataset.mobileTabbar = "true";
  nav.setAttribute("aria-label", "Navegación rápida");
  nav.append(
    createTabButton("agenda", "⌂", "Agenda"),
    createTabButton("search", "⌕", "Buscar"),
    createTabButton("plans", "★", "Mis planes"),
    createTabButton("city", "⌖", "Ciudad"),
  );
  document.body.append(nav);
  return nav;
}

const tabbar = buildTabbar();

function setActive(action) {
  for (const button of tabbar.querySelectorAll("[data-mobile-action]")) {
    if (button.dataset.mobileAction === action) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
}

function scrollToNode(node) {
  node?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function openSearch() {
  const toggle = document.querySelector("[data-header-search-toggle]");
  if (!toggle) return;
  toggle.click();
  setActive("search");
}

function openPlans() {
  const section = document.querySelector("[data-my-plans]");
  scrollToNode(section || document.querySelector("[data-agenda]"));
  setActive("plans");
}

function openCityChooser() {
  document.querySelector("[data-city-switch]")?.click();
  setActive("city");
}

function openAgenda() {
  scrollToNode(document.querySelector("[data-agenda]") || document.querySelector("main"));
  setActive("agenda");
}

tabbar.addEventListener("click", (event) => {
  const button = event.target.closest("[data-mobile-action]");
  if (!button) return;
  const actions = { agenda: openAgenda, search: openSearch, plans: openPlans, city: openCityChooser };
  actions[button.dataset.mobileAction]?.();
});

function syncCityOptionState() {
  const city = document.documentElement.dataset.city;
  for (const option of document.querySelectorAll("[data-city-option]")) {
    if (option.dataset.cityOption === city) option.setAttribute("aria-current", "true");
    else option.removeAttribute("aria-current");
  }
}

function syncModalVisibility() {
  const openModal = [...document.querySelectorAll(".chooser-backdrop")]
    .some((node) => !node.hidden);
  tabbar.hidden = openModal;
  if (!openModal && document.documentElement.dataset.city) setActive("agenda");
}

function restoreChooserCopyForManualSwitch() {
  if (chooserBackdrop?.dataset.selectionRequired === "true") return;
  const title = document.querySelector("#chooser-title");
  const intro = document.querySelector("[data-chooser] > p:not(.eyebrow)");
  if (title) title.textContent = "Cambiar ciudad";
  if (intro) intro.textContent = "La ciudad que elijas quedará guardada como tu agenda habitual. Podrás cambiarla de nuevo cuando quieras.";
}

document.querySelector("[data-city-switch]")?.addEventListener("click", restoreChooserCopyForManualSwitch);

new MutationObserver(() => {
  syncCityOptionState();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

new MutationObserver(syncModalVisibility).observe(document.body, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["hidden"],
});

window.addEventListener("appinstalled", syncStandaloneFlag);
standaloneQuery?.addEventListener?.("change", syncStandaloneFlag);
window.matchMedia?.(MOBILE_QUERY)?.addEventListener?.("change", syncModalVisibility);

syncStandaloneFlag();
syncCityOptionState();
syncModalVisibility();
setActive("agenda");
