(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v164 adds the faster startup cache strategy while preserving bounded freshness for agenda data.
  const RELEASE = 164;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();