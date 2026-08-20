(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v150 also classifies long formation cycles without explicit sessions as programs,
  // so they do not appear as daily "Hoy" events or inherit venue opening hours.
  const RELEASE = 150;
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
