(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v130 keeps the v129 grouping fixes and isolates contextual filters between
  // cities, with a fail-open guard if the secondary filter dataset fetch fails.
  const RELEASE = 130;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
