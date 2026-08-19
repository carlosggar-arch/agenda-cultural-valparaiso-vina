(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v140 preserves the v139 Valpo/Viña card repairs and reloads the app on a
  // real city change so each city starts with its correct city-specific runtime.
  const RELEASE = 140;
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
