import "./vivamos-brand.js";
import "./card-experience.js";
import "./schedule-display.js";
import "./card-image-fallback.js";
import "./compact-top.js";
import "./gijon-visual-reference.js";
import "./sources-toggle.js";
import "./community-source.js";
import "./header-redesign.js";
import "./density-polish.js";
import "./combined-filters-polish.js";
import "./plan-ahead.js";
import "./favorites.js";

const APP_VERSION = "PWA v33";
const versionNode = document.querySelector("[data-app-version]");
if (versionNode) versionNode.textContent = APP_VERSION;

let deferredInstallPrompt = null;
const installButton = document.querySelector("[data-install-app]");

function isRunningStandalone() {
  return window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

function isIosLike() {
  const ua = navigator.userAgent || "";
  return /iPad|iPhone|iPod/i.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function hideInstallButton() {
  if (!installButton) return;
  installButton.hidden = true;
  installButton.disabled = false;
  deferredInstallPrompt = null;
}

function installHelpElement() {
  let backdrop = document.querySelector("[data-install-help-backdrop]");
  if (backdrop) return backdrop;
  backdrop = document.createElement("div");
  backdrop.className = "chooser-backdrop";
  backdrop.dataset.installHelpBackdrop = "true";
  backdrop.hidden = true;
  backdrop.innerHTML = `<section class="chooser" role="dialog" aria-modal="true" aria-labelledby="install-help-title"><button class="chooser-close" type="button" aria-label="Cerrar" data-install-help-close>×</button><p class="eyebrow">Instalar ¡Vivamos!</p><h2 id="install-help-title">Añádela a tu pantalla de inicio</h2><p>En iPhone o iPad, abre el menú <strong>Compartir</strong> del navegador y elige <strong>Añadir a pantalla de inicio</strong>.</p><p class="privacy-note">Después se abrirá como una app independiente y conservará tu ciudad preferida.</p></section>`;
  document.body.append(backdrop);
  const close = () => { backdrop.hidden = true; };
  backdrop.querySelector("[data-install-help-close]")?.addEventListener("click", close);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) close(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !backdrop.hidden) close(); });
  return backdrop;
}

function showInstallHelp() {
  installHelpElement().hidden = false;
}

function setupInstallExperience() {
  if (!installButton || isRunningStandalone()) return;
  if (isIosLike()) {
    installButton.hidden = false;
    installButton.addEventListener("click", showInstallHelp);
  }
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    installButton.hidden = false;
  });
  installButton.addEventListener("click", async () => {
    if (!deferredInstallPrompt) return;
    const promptEvent = deferredInstallPrompt;
    deferredInstallPrompt = null;
    installButton.disabled = true;
    try {
      await promptEvent.prompt();
      const choice = await promptEvent.userChoice;
      if (choice?.outcome === "accepted") hideInstallButton();
      else {
        installButton.disabled = false;
        installButton.hidden = false;
      }
    } catch (error) {
      installButton.disabled = false;
      installButton.hidden = false;
      console.warn("¡Vivamos!: install prompt unavailable", error);
    }
  });
  window.addEventListener("appinstalled", hideInstallButton, { once: true });
}

async function registerAgendaServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  try {
    const registration = await navigator.serviceWorker.register("./service-worker.js", { scope: "./", updateViaCache: "none" });
    registration.update().catch(() => {});
  } catch (error) {
    console.warn("¡Vivamos!: service worker unavailable", error);
  }
}

setupInstallExperience();
registerAgendaServiceWorker();
