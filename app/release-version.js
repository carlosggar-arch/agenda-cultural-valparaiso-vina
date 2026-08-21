(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v167 consolidates filter visibility and grouped-exhibition presentation under single owners.
  const RELEASE = 167;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
