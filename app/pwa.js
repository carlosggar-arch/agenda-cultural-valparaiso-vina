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

window.addEventListener("load", registerAgendaServiceWorker, { once: true });
