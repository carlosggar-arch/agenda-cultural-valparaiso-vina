(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v174 makes cross-source deduplication resilient to incorrect upstream official flags for direct venue sources.
  const RELEASE = 174;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
