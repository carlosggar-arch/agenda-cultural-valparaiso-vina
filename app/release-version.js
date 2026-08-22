(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v190 consolidates all public schedule presentation under schedule-display.
  const RELEASE = 190;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
