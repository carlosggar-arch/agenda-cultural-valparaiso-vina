(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v110 removes the public like control while retaining private install analytics.
  const RELEASE = 110;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
