import "./vivamos-brand.js";
import "./card-experience.js";
import "./schedule-display.js";
import "./card-image-fallback.js";
import "./compact-top.js";
import "./gijon-visual-reference.js";
import "./lean-filters.js";
import "./sources-toggle.js";
import "./community-source.js";
import "./header-redesign.js";
import "./density-polish.js";

const APP_VERSION = "PWA v23";
const versionNode = document.querySelector("[data-app-version]");
if (versionNode) versionNode.textContent = APP_VERSION;

let deferredInstallPrompt = null;
const installButton = document.querySelector("[data-install-app]");

function isRunningStandalone() {
  return window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

function hideInstallButton() {
  if (!installButton) return;
  installButton.hidden = true;
  installButton.disabled = false;
  deferredInstallPrompt = null;
}

function setupInstallExperience() {
  if (!installButton || isRunningStandalone()) return;

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
      if (choice?.outcome === "accepted") {
        hideInstallButton();
      } else {
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
    const registration = await navigator.serviceWorker.register("./service-worker.js", {
      scope: "./",
      updateViaCache: "none",
    });

    registration.update().catch(() => {});
  } catch (error) {
    console.warn("¡Vivamos!: service worker unavailable", error);
  }
}

setupInstallExperience();
registerAgendaServiceWorker();