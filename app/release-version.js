(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v220 publishes the unified multi-city source registry contract.
  const RELEASE = 220;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
