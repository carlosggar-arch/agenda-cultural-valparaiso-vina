(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  const RELEASE = 69;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
