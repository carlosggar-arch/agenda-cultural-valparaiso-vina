(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v113 removes the retired like placeholder, fills the six-button mobile rail,
  // and suppresses legacy loading states during first paint.
  const RELEASE = 113;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
