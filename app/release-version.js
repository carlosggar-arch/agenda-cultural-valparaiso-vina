(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v187 adds the shared voluntary support link with PayPal.
  const RELEASE = 187;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
