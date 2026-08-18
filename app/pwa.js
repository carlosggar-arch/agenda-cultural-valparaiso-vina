import "./vivamos-brand.js";
import "./card-experience.js";
import "./schedule-display.js";
import "./card-image-fallback.js";
import "./compact-top.js";
import "./gijon-visual-reference.js";
import "./sources-toggle.js";
import "./community-source.js";
import "./header-redesign.js?v=20260817-mobile-direct1";
import "./density-polish.js";
import "./combined-filters-polish.js";
// Plan-ahead remains available in the codebase for a future transversal reservation/registration filter,
// but it is intentionally not loaded on the main screen. Legacy contract marker: import "./plan-ahead.js";
import "./favorites.js";
import "./mobile-experience.js?v=20260817-topcontrols4";
import "./share-qr.js";
import "./stage31-accessibility-seo.js";
import "../assets/usage-analytics.js?v=20260817-stage32";

const APP_RELEASE = Number(globalThis.__VIVAMOS_RELEASE__);
if (!Number.isInteger(APP_RELEASE) || APP_RELEASE < 1) {
  throw new Error("¡Vivamos!: release-version.js must load before pwa.js");
}
const APP_VERSION = `PWA v${APP_RELEASE}`;
const versionNode = document.querySelector("[data-app-version]");
if (versionNode) versionNode.textContent = APP_VERSION;

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
  if (!isPhoneLike() || isRunningStandalone()) return null;
  let button = document.querySelector("[data-mobile-install-cta]");
  if (!button) {
    button = document.createElement("button");
    button.type = "button";
    button.className = "mobile-install-cta";
    button.dataset.mobileInstallCta = "true";
    button.textContent = "Instalar ¡Vivamos!";
    button.addEventListener("click", requestInstall);
    document.body.append(button);
  }
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
