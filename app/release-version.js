(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v218 serves optimized, provenance-preserving official images from the
  // publication itself for every registered city.
  const RELEASE = 218;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
