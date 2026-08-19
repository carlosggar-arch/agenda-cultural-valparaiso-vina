(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v131 keeps the v130 city-isolation fixes and makes schedule-display consume
  // the normalized data pipeline so all structured cinema sessions stay visible.
  const RELEASE = 131;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
