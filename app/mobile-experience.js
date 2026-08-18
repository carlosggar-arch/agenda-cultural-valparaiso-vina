const MOBILE_QUERY = "(max-width: 900px)";
const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
const chooserBackdrop = document.querySelector("[data-chooser-backdrop]");
const TABBAR_ID = "vivamos-mobile-tabbar";

function ensureMeta(name, content) {
  let meta = document.head.querySelector(`meta[name="${name}"]`);
  if (!meta) {
    meta = document.createElement("meta");
    meta.name = name;
    document.head.append(meta);
  }
  meta.content = content;
}

function installMobileMetadata() {
  ensureMeta("application-name", "¡Vivamos!");
  ensureMeta("mobile-web-app-capable", "yes");
  ensureMeta("apple-mobile-web-app-capable", "yes");
  ensureMeta("apple-mobile-web-app-title", "¡Vivamos!");
  ensureMeta("apple-mobile-web-app-status-bar-style", "default");
}

function installMobileStyles() {
  const href = "./mobile-experience.css?v=20260817-topnav9";
  const links = [...document.querySelectorAll('link[href*="mobile-experience.css"]')];
  if (links.length) {
    links[0].href = href;
    for (const extra of links.slice(1)) extra.remove();
    return;
  }
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  link.dataset.mobileExperienceStyles = "true";
  document.head.append(link);
}

function isStandalone() {
  return Boolean(standaloneQuery?.matches || window.navigator.standalone === true);
}

function isMobileClient() {
  const uaMobile = navigator.userAgentData?.mobile === true
    || /Android|iPhone|iPad|iPod|Mobile|IEMobile|Opera Mini/i.test(String(navigator.userAgent || ""));
  const screenWidth = Number(screen.width || 9999);
  const viewportWidth = Number(window.innerWidth || document.documentElement.clientWidth || 9999);
  return isStandalone() || uaMobile || screenWidth <= 900 || viewportWidth <= 900;
}

function syncClientFlags() {
  document.documentElement.dataset.standalone = String(isStandalone());
  document.documentElement.dataset.mobileClient = String(isMobileClient());
}

function createTabButton(action, icon, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.mobileAction = action;
  button.setAttribute("aria-label", label);
  button.innerHTML = `<span class="mobile-tab-icon" aria-hidden="true">${icon}</span><span>${label}</span>`;
  return button;
}

function dedupeTabbars(keep) {
  for (const node of document.querySelectorAll("[data-mobile-tabbar], .mobile-tabbar")) {
    if (node !== keep) node.remove();
  }
}

function buildTabbar() {
  let nav = document.getElementById(TABBAR_ID);
  if (!nav) {
    nav = document.querySelector("[data-mobile-tabbar], .mobile-tabbar");
  }
  if (!nav) {
    nav = document.createElement("nav");
    nav.append(
      createTabButton("agenda", "⌂", "Agenda"),
      createTabButton("search", "⌕", "Buscar"),
      createTabButton("plans", "★", "Mis planes"),
      createTabButton("city", "⌖", "Ciudad"),
    );
  }
  nav.id = TABBAR_ID;
  nav.className = "mobile-tabbar mobile-topnav";
  nav.dataset.mobileTabbar = "true";
  nav.setAttribute("aria-label", "Navegación rápida");
  dedupeTabbars(nav);
  const host = document.querySelector(".app-header");
  if (host && nav.parentElement !== host) host.append(nav);
  nav.hidden = false;
  return nav;
}

installMobileMetadata();
installMobileStyles();
syncClientFlags();
const tabbar = buildTabbar();

function ensureTabbarMounted() {
  dedupeTabbars(tabbar);
  const host = document.querySelector(".app-header");
  if (host && tabbar.parentElement !== host) host.append(tabbar);
  tabbar.hidden = false;
}

function setActive(action) {
  for (const button of tabbar.querySelectorAll("[data-mobile-action]")) {
    if (button.dataset.mobileAction === action) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
}

function scrollToNode(node) { node?.scrollIntoView({ behavior: "smooth", block: "start" }); }
function openSearch() { const toggle = document.querySelector("[data-header-search-toggle]"); if (!toggle) return; toggle.click(); setActive("search"); }
function openPlans() { const section = document.querySelector("[data-my-plans]"); const disclosure = section?.querySelector(".my-plans-disclosure"); if (disclosure) disclosure.open = true; scrollToNode(section || document.querySelector("[data-agenda]")); setActive("plans"); }
function openCityChooser() { document.querySelector("[data-city-switch]")?.click(); setActive("city"); }
function openAgenda() { scrollToNode(document.querySelector("[data-agenda]") || document.querySelector("main")); setActive("agenda"); }

tabbar.addEventListener("click", (event) => {
  const button = event.target.closest("[data-mobile-action]");
  if (!button) return;
  const actions = { agenda: openAgenda, search: openSearch, plans: openPlans, city: openCityChooser };
  actions[button.dataset.mobileAction]?.();
});

function syncCityOptionState() {
  const city = document.documentElement.dataset.city;
  const selectionRequired = chooserBackdrop?.dataset.selectionRequired === "true";
  for (const option of document.querySelectorAll("[data-city-option]")) {
    if (!selectionRequired && option.dataset.cityOption === city) option.setAttribute("aria-current", "true");
    else option.removeAttribute("aria-current");
  }
}

function syncMobileUi() {
  syncClientFlags();
  ensureTabbarMounted();
  if (document.documentElement.dataset.city) setActive("agenda");
}

function observeModal(node) {
  if (!node || node.dataset.mobileObserved === "true") return;
  node.dataset.mobileObserved = "true";
  new MutationObserver(() => { syncMobileUi(); syncCityOptionState(); })
    .observe(node, { attributes: true, attributeFilter: ["hidden", "data-selection-required"] });
}

function restoreChooserCopyForManualSwitch() {
  if (chooserBackdrop?.dataset.selectionRequired === "true") return;
  const title = document.querySelector("#chooser-title");
  const intro = document.querySelector("[data-chooser] > p:not(.eyebrow)");
  if (title) title.textContent = "Cambiar ciudad";
  if (intro) intro.textContent = "La ciudad que elijas quedará guardada como tu agenda habitual. Podrás cambiarla de nuevo cuando quieras.";
}

document.querySelector("[data-city-switch]")?.addEventListener("click", restoreChooserCopyForManualSwitch);
new MutationObserver(syncCityOptionState).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
observeModal(chooserBackdrop);
for (const modal of document.querySelectorAll(".chooser-backdrop")) observeModal(modal);
new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (!(node instanceof Element)) continue;
      if (node.matches?.(".chooser-backdrop")) observeModal(node);
      for (const modal of node.querySelectorAll?.(".chooser-backdrop") || []) observeModal(modal);
    }
  }
  syncMobileUi();
}).observe(document.body, { childList: true, subtree: true });

window.addEventListener("appinstalled", syncMobileUi);
window.addEventListener("resize", syncMobileUi);
window.addEventListener("orientationchange", syncMobileUi);
standaloneQuery?.addEventListener?.("change", syncMobileUi);
window.matchMedia?.(MOBILE_QUERY)?.addEventListener?.("change", syncMobileUi);

syncCityOptionState();
syncMobileUi();
setActive("agenda");
