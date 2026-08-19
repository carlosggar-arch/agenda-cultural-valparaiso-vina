(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v139 preserves the v138 date-filter/cache architecture and repairs cards
  // that exist only in the normalized Valpo/Viña pipeline, including grouped
  // Palacio Rioja activities and honest image fallbacks.
  const RELEASE = 139;
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
