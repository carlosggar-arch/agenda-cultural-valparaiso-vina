const MOBILE_QUERY = "(max-width: 900px)";
const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
const chooserBackdrop = document.querySelector("[data-chooser-backdrop]");

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

function verifyMobileStyles() {
  const link = document.head.querySelector('link[data-mobile-experience-styles][href*="mobile-experience.css"]');
  if (!link) console.error("¡Vivamos!: mobile-experience.css must load from <head> before first paint");
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

function removeRetiredTabbars(root = document) {
  const nodes = [];
  if (root instanceof Element && (root.matches("[data-mobile-tabbar]") || root.matches(".mobile-tabbar"))) nodes.push(root);
  for (const node of root.querySelectorAll?.("[data-mobile-tabbar], .mobile-tabbar") || []) nodes.push(node);
  for (const node of new Set(nodes)) node.remove();
}

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
  removeRetiredTabbars();
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

installMobileMetadata();
verifyMobileStyles();
syncClientFlags();
removeRetiredTabbars();

document.querySelector("[data-city-switch]")?.addEventListener("click", restoreChooserCopyForManualSwitch);
new MutationObserver(syncCityOptionState).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
observeModal(chooserBackdrop);
for (const modal of document.querySelectorAll(".chooser-backdrop")) observeModal(modal);

new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (!(node instanceof Element)) continue;
      removeRetiredTabbars(node);
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
