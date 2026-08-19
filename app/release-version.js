(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v142 keeps the v141 monthly-listing fix and preserves normalized public
  // titles after Valpo/Viña rich-card enrichment rehydrates cards from raw data.
  const RELEASE = 142;
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
