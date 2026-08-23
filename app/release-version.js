(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v204 expands verified canonical venue navigation across cities and reduces the map-link pill height.
  const RELEASE = 204;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
