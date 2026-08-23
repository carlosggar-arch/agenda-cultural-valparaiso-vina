// Contract references for shell-version tests; these are documentation only, not eager imports.
// import "./header-redesign.js?v=20260817-brandicon2";
// import "./mobile-experience.js?v=20260817-topcontrols4";
// import "./combined-filters-polish.js";
// import "./favorites.js";
// import "./stage31-accessibility-seo.js";
// Plan-ahead remains available for a future transversal reservation/registration filter.
// import "./plan-ahead.js";

// pwa.js owns shell/install/UI-only behavior. Content presentation is owned once
// by app.js so query-string aliases cannot instantiate duplicate card observers
// or duplicate dataset consumers in the same page. In particular, sources,
// community-source and participation-footer are app.js-owned content modules.
const OPTIONAL_UI_MODULES = [
  "./vivamos-brand.js",
  "./compact-top.js",
  "./gijon-visual-reference.js",
  "./remove-like.js?v=20260819-remove3",
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

if (String(document.documentElement.dataset.city || "") === "gijon") {
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

function isIosLike() {
  const ua = String(navigator.userAgent || "");
  const classicIos = /iPhone|iPad|iPod/i.test(ua);
  const ipadDesktopMode = /Macintosh/i.test(ua) && Number(navigator.maxTouchPoints || 0) > 1;
  return classicIos || ipadDesktopMode;
}

function installHelpContent() {
  if (isIosLike()) {
    return `<section class="chooser install-help install-help-ios" role="dialog" aria-modal="true" aria-labelledby="install-help-title"><button class="chooser-close" type="button" aria-label="Cerrar" data-install-help-close>×</button><p class="eyebrow">Instalar ¡Vivamos!</p><h2 id="install-help-title">Añádela a tu iPhone</h2><p class="install-help-lead">Solo necesitas hacerlo una vez. Después se abrirá desde su propio icono, como cualquier aplicación.</p><ol class="install-help-steps"><li><span class="install-step-icon" aria-hidden="true">↥</span><span><small>Paso 1</small>Pulsa <strong>Compartir</strong> en el navegador.</span></li><li><span class="install-step-icon" aria-hidden="true">＋</span><span><small>Paso 2</small>Elige <strong>Añadir a pantalla de inicio</strong>.</span></li><li><span class="install-step-icon install-step-toggle" aria-hidden="true">●</span><span><small>Paso 3</small>Activa <strong>Abrir como app</strong>, si aparece.</span></li><li><span class="install-step-icon" aria-hidden="true">✓</span><span><small>Paso 4</small>Pulsa <strong>Añadir</strong>.</span></li></ol><p class="install-help-result"><span aria-hidden="true">⌂</span> Encontrarás <strong>¡Vivamos!</strong> en tu pantalla de inicio.</p><p class="privacy-note">Si no aparece esa opción, abre el enlace en Safari y vuelve a pulsar Compartir.</p></section>`;
  }
  return `<section class="chooser" role="dialog" aria-modal="true" aria-labelledby="install-help-title"><button class="chooser-close" type="button" aria-label="Cerrar" data-install-help-close>×</button><p class="eyebrow">Instalar ¡Vivamos!</p><h2 id="install-help-title">Instala la aplicación</h2><p>Abre el menú del navegador (<strong>⋮</strong> o <strong>Compartir</strong>) y elige <strong>Instalar aplicación</strong> o <strong>Añadir a pantalla de inicio</strong>.</p><p class="privacy-note">Después se abrirá como una app independiente y conservará tu ciudad preferida.</p></section>`;
}

function installHelpElement() {
  let backdrop = document.querySelector("[data-install-help-backdrop]");
  if (backdrop) return backdrop;
  backdrop = document.createElement("div");
  backdrop.className = "chooser-backdrop";
  backdrop.dataset.installHelpBackdrop = "true";
  backdrop.hidden = true;
  backdrop.innerHTML = installHelpContent();
  document.body.append(backdrop);
  const close = () => { backdrop.hidden = true; };
  backdrop.querySelector("[data-install-help-close]")?.addEventListener("click", close);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) close(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !backdrop.hidden) close(); });
  return backdrop;
}

function showInstallHelp() {
  const backdrop = installHelpElement();
  backdrop.hidden = false;
  backdrop.querySelector("[data-install-help-close]")?.focus?.({ preventScroll: true });
}

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
  button.textContent = isIosLike() && !deferredInstallPrompt ? "Cómo instalar ¡Vivamos!" : "Instalar ¡Vivamos!";
  button.setAttribute("aria-label", isIosLike() && !deferredInstallPrompt ? "Cómo instalar ¡Vivamos! en iPhone o iPad" : (installIntent ? "Instalar la aplicación ¡Vivamos!" : "Instalar ¡Vivamos!"));
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

function showExplicitIosInstallIntent() {
  if (!installIntent || !isIosLike() || isRunningStandalone()) return;
  const reveal = () => {
    if (isRunningStandalone() || deferredInstallPrompt) return;
    const chooser = document.querySelector("[data-chooser-backdrop]");
    if (chooser && !chooser.hidden) {
      const observer = new MutationObserver(() => {
        if (!chooser.hidden) return;
        observer.disconnect();
        showInstallHelp();
      });
      observer.observe(chooser, { attributes: true, attributeFilter: ["hidden"] });
      return;
    }
    showInstallHelp();
  };
  queueMicrotask(reveal);
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
showExplicitIosInstallIntent();
registerAgendaServiceWorker();
