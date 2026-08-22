(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v182 unifies presentation modules across cities and removes legacy card renderers.
  const RELEASE = 182;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();