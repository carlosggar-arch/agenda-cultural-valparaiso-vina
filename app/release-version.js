(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v223 publishes the current verified main state through the canonical production flow.
  const RELEASE = 223;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
