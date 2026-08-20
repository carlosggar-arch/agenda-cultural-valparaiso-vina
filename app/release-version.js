(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v149 rejects generic event images, normalizes partial all-caps titles and prunes expired sessions.
  const RELEASE = 149;
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
