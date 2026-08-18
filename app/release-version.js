(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  const RELEASE = 59;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
