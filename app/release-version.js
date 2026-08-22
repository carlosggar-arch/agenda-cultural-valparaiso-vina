(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v198 reuses the canonical runtime dataset for favorites and sources, avoiding duplicate dataset downloads/parses.
  const RELEASE = 198;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
