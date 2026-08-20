(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v152 moves the public share/install QR to vivamos.pages.dev while keeping
  // the GitHub Pages and Cloudflare deployments on the same application code.
  const RELEASE = 152;
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
