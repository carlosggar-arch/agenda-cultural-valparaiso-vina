(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v144 centralizes normalized runtime state, removes body-wide presentation
  // observers, and gives app.js sole ownership of content presentation modules.
  const RELEASE = 144;
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
