(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v211 adds semantic smart-search terms and the corresponding release guards.
  const RELEASE = 211;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
