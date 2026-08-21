(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v168 refreshes the PWA cache generation after the latest runtime updates.
  const RELEASE = 168;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
