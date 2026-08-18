(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  const RELEASE = 85;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();