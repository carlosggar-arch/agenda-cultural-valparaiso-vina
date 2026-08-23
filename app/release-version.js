(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v207 invalidates the shell cache for the mixed date-range lifecycle fix.
  const RELEASE = 207;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
