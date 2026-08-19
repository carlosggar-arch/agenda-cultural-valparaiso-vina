(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v141 keeps the v140 city-runtime reload and prevents generic monthly
  // listings such as Destino Valparaíso — Agosto 2026 from becoming Hoy cards.
  const RELEASE = 141;
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
