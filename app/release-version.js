(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v137 hardens date-filter single-source behavior and forces existing controlled
  // tabs to reload once when the fresh service worker takes control.
  const RELEASE = 137;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;

  if (typeof window !== "undefined" && "serviceWorker" in navigator && navigator.serviceWorker.controller) {
    let refreshedForControllerChange = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (refreshedForControllerChange) return;
      refreshedForControllerChange = true;
      window.location.reload();
    });
  }
})();
