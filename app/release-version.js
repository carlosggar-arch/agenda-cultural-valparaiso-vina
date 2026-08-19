(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v137 keeps the recovered v136 toolbar/feed and restores Valpo/Vina card
  // images while keeping valid dated events visible without confidence metadata.
  const RELEASE = 137;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
