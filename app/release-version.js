(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  const RELEASE = 68;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
