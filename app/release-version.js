(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  const RELEASE = 61;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
