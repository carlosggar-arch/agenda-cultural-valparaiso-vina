// Contract references for shell-version tests; these are documentation only, not eager imports.
// import "./header-redesign.js?v=20260817-brandicon2";
// import "./mobile-experience.js?v=20260817-topcontrols4";
// import "./schedule-display.js?v=20260819-hours3";
// import "./combined-filters-polish.js";
// import "./favorites.js";
// import "./stage31-accessibility-seo.js";
// Plan-ahead remains available for a future transversal reservation/registration filter.
// import "./plan-ahead.js";

const OPTIONAL_UI_MODULES = [
  "./vivamos-brand.js",
  "./card-experience.js",
  "./public-presentation-guard.js",
  "./schedule-display.js?v=20260819-hours3",
  "./exhibition-hours.js?v=20260818-hours2",
  "./card-image-fallback.js",
  "./compact-top.js",
  "./gijon-visual-reference.js",
  "./sources-toggle.js",
  "./community-source.js?v=20260818-feedback3",
  "./remove-like.js?v=20260819-remove3",
  "./participation-footer.js?v=20260819-feedback7",
  "./header-redesign.js?v=20260817-brandicon2",
  "./density-polish.js",
  "./combined-filters-polish.js",
  "./favorites.js",
  "./mobile-experience.js?v=20260817-topcontrols4",
  "./installed-mosaic.js?v=20260818-f12-dual4",
  "./mobile-action-strip-six.js?v=20260819-actions7",
  "./share-qr.js?v=20260818-installqr1",
  "./web-actions-below-mosaic.js?v=20260818-web2",
  "./action-strip-layout.js?v=20260818-fill1",
  "./stage31-accessibility-seo.js",
  "../assets/usage-analytics.js?v=20260817-stage32",
];

// Several presentation enhancers watch and rewrite the same card subtree. On the
// larger Gijon agenda that observer stack can keep the main thread busy after the
// core render, and card-experience.css can also style an unenhanced card if its
// secondary dataset request stalls. Keep those observer-heavy layers out of the
// Gijon runtime until they are refactored to explicit render hooks. The stable
// core cards remain complete, filterable and readable without them.
const GIJON_DEFERRED_UI_MODULES = new Set([
  "./card-experience.js",
  "./public-presentation-guard.js",
  "./schedule-display.js?v=20260819-hours3",
  "./exhibition-hours.js?v=20260818-hours2",
  "./card-image-fallback.js",
]);
if (String(document.documentElement.dataset.city || "") === "gijon") {
  for (let index = OPTIONAL_UI_MODULES.length - 1; index >= 0; index -= 1) {
    if (GIJON_DEFERRED_UI_MODULES.has(OPTIONAL_UI_MODULES[index])) OPTIONAL_UI_MODULES.splice(index, 1);
  }
  document.documentElement.dataset.gijonStableUi = "true";
}

let optionalUiStarted = false;

async function loadOptionalUiModules() {
  if (optionalUiStarted || document.documentElement.dataset.vivamosSafeMode === "active") return;
  optionalUiStarted = true;
  const results = await Promise.allSettled(OPTIONAL_UI_MODULES.map((module) => import(module)));
  results.forEach((result, index) => {
    if (result.status === "rejected") console.warn(`¡Vivamos!: módulo PWA opcional omitido (${OPTIONAL_UI_MODULES[index]})`, result.reason);
  });
}

function scheduleOptionalUiModules() {
  if (document.documentElement.dataset.vivamosSafeMode === "active") return;
  queueMicrotask(() => { void loadOptionalUiModules(); });
}

if (document.documentElement.dataset.vivamosReady === "true") scheduleOptionalUiModules();
else window.addEventListener("vivamos:core-ready", scheduleOptionalUiModules, { once: true });

const APP_RELEASE = Number(globalThis.__VIVAMOS_RELEASE__);
if (!Number.isInteger(APP_RELEASE) || APP_RELEASE < 1) {
  throw new Error("¡Vivamos!: release-version.js must load before pwa.js");
}
const APP_VERSION = `PWA v${APP_RELEASE}`;
const versionNode = document.querySelector("[data-app-version]");
if (versionNode) versionNode.textContent = APP_VERSION;

const installIntent = new URLSearchParams(window.location.search).get("install") === "1";
let deferredInstallPrompt = null;
const installButton = document.querySelector("[data-install-app]");
let mobileInstallButton = null;

function isRunningStandalone() {
  return window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

function isPhoneLike() {
  const uaMobile = navigator.userAgentData?.mobile === true
    || /Android|iPhone|iPad|iPod|Mobile|IEMobile|Opera Mini/i.test(String(navigator.userAgent || ""));
  const screenWidth = Number(screen.width || 9999);
  const viewportWidth = Number(window.innerWidth || document.documentElement.clientWidth || 9999);
  return uaMobile || screenWidth <= 900 || viewportWidth <= 900;
}

function installHelpElement() {
  let backdrop = document.querySelector("[data-install-help-backdrop]");
  if (backdrop) return backdrop;
  backdrop = document.createElement("div");
  backdrop.className = "chooser-backdrop";
  backdrop.dataset.installHelpBackdrop = "true";
  backdrop.hidden = true;
  backdrop.innerHTML = `<section class="chooser" role="dialog" aria-modal="true" aria-labelledby="install-help-title"><button class="chooser-close" type="button" aria-label="Cerrar" data-install-help-close>×</button><p class="eyebrow">Instalar ¡Vivamos!</p><h2 id="install-help-title">Instala la aplicación</h2><p>Abre el menú del navegador (<strong>⋮</strong> o <strong>Compartir</strong>) y elige <strong>Instalar aplicación</strong> o <strong>Añadir a pantalla de inicio</strong>.</p><p class="privacy-note">Después se abrirá como una app independiente y conservará tu ciudad preferida.</p></section>`;
  document.body.append(backdrop);
  const close = () => { backdrop.hidden = true; };
  backdrop.querySelector("[data-install-help-close]")?.addEventListener("click", close);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) close(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !backdrop.hidden) close(); });
  return backdrop;
}

function showInstallHelp() { installHelpElement().hidden = false; }

async function requestInstall() {
  if (!deferredInstallPrompt) { showInstallHelp(); return; }
  const promptEvent = deferredInstallPrompt;
  deferredInstallPrompt = null;
  for (const button of [installButton, mobileInstallButton]) if (button) button.disabled = true;
  try {
    await promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    if (choice?.outcome === "accepted") hideInstallButtons();
    else for (const button of [installButton, mobileInstallButton]) if (button) button.disabled = false;
  } catch (error) {
    for (const button of [installButton, mobileInstallButton]) if (button) button.disabled = false;
    showInstallHelp();
    console.warn("¡Vivamos!: install prompt unavailable", error);
  }
}

function ensureMobileInstallButton() {
  if ((!isPhoneLike() && !installIntent) || isRunningStandalone()) return null;
  let button = document.querySelector("[data-mobile-install-cta]");
  if (!button) {
    button = document.createElement("button");
    button.type = "button";
    button.className = "mobile-install-cta";
    button.dataset.mobileInstallCta = "true";
    button.addEventListener("click", requestInstall);
    document.body.append(button);
  }
  button.textContent = "Instalar ¡Vivamos!";
  button.setAttribute("aria-label", installIntent ? "Instalar la aplicación ¡Vivamos!" : "Instalar ¡Vivamos!");
  if (installIntent) button.dataset.installPriority = "true";
  else delete button.dataset.installPriority;
  mobileInstallButton = button;
  return button;
}

function hideInstallButtons() {
  if (installButton) { installButton.hidden = true; installButton.disabled = false; }
  if (mobileInstallButton) { mobileInstallButton.remove(); mobileInstallButton = null; }
  deferredInstallPrompt = null;
}

function setupInstallExperience() {
  if (isRunningStandalone()) { hideInstallButtons(); return; }
  if (installButton) { installButton.hidden = false; installButton.addEventListener("click", requestInstall); }
  ensureMobileInstallButton();
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    if (installButton) installButton.hidden = false;
    ensureMobileInstallButton();
  });
  window.addEventListener("appinstalled", hideInstallButtons, { once: true });
}

async function registerAgendaServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  try {
    const registration = await navigator.serviceWorker.register(`./service-worker.js?v=${APP_RELEASE}`, { scope: "./", updateViaCache: "none" });
    registration.update().catch(() => {});
  } catch (error) {
    console.warn("¡Vivamos!: service worker unavailable", error);
  }
}

setupInstallExperience();
registerAgendaServiceWorker();