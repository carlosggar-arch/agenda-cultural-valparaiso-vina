(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  const RELEASE = 88;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
