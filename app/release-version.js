(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v145 applies the shared public-title cleanup consistently in Valpo/Viña
  // and Gijón, including all-caps, redundant format labels, and outer quotes.
  const RELEASE = 145;
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
