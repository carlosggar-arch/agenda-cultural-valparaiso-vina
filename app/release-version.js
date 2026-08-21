(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v166 combines generated release/venue contracts with grouped-exhibition filter isolation.
  const RELEASE = 166;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
