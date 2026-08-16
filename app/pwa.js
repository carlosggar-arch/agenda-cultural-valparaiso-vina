import "./card-experience.js";
import "./card-image-fallback.js";

const APP_VERSION = "PWA v5";
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
      console.warn("Agenda Cultural: install prompt unavailable", error);
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

    // Ask for a fresh worker definition on each full app load. The worker itself
    // uses versioned caches, so an update remains atomic and scoped to /app/.
    registration.update().catch(() => {});
  } catch (error) {
    console.warn("Agenda Cultural: service worker unavailable", error);
  }
}

setupInstallExperience();
window.addEventListener("load", registerAgendaServiceWorker, { once: true });
