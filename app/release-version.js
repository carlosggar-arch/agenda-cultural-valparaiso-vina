(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v151 corrects Artequin's "El arte es natural" to its four official Friday sessions,
  // preventing the workshop from appearing as a continuous daily "Hoy" event.
  const RELEASE = 151;
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
