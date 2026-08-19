(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v138 preserves the v137 Valpo/Vina image + dated-event fixes, hardens
  // single-source date filtering, and refreshes already-controlled tabs once
  // when the fresh service worker takes control.
  const RELEASE = 138;
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
