(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v189 consolidates event-card and grouped-row visibility under one owner.
  const RELEASE = 189;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
