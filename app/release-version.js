(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v143 keeps the v142 normalized-title guard and forces the repaired Valpo/Viña
  // runtime-card image fallback to replace any cached pre-repair module instance.
  const RELEASE = 143;
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
