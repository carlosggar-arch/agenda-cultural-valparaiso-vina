(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v148 keeps Cine as the primary category for Los Fantasmas and also exposes it under Teatro.
  const RELEASE = 148;
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
