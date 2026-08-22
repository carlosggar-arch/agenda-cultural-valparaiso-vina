(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v200 refreshes the shared presentation module cache keys so Google Maps navigation is delivered immediately.
  const RELEASE = 200;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();