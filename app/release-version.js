(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v171 keeps the mobile startup improvements and publishes the exhibition venue deduplication/order fix.
  const RELEASE = 171;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
