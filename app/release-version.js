(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v180 unifies exhibition grouping and date-specific venue hours across cities.
  const RELEASE = 180;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();