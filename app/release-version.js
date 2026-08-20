(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v153 restores the public Fuentes control in the footer and refreshes the
  // cached application shell so existing PWA installations receive the fix.
  const RELEASE = 153;
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
