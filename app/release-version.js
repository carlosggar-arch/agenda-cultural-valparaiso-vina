(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v146 keeps both weekend filters aligned on Friday through Sunday.
  const RELEASE = 146;
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
