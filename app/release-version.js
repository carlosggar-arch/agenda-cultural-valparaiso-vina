(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v175 makes cross-source deduplication resilient to incorrect upstream official flags for direct venue sources.
  const RELEASE = 175;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
