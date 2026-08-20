(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v158 adds structural public-text sanitation so source HTML can never leak
  // into visible agenda labels, titles, descriptions, schedules or locations.
  const RELEASE = 158;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
