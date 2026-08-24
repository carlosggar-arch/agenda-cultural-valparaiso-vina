(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v221 publishes structural event-series session expansion.
  const RELEASE = 221;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
