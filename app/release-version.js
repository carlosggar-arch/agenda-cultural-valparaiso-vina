(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v185 publishes shared schedule preservation, date-aware venue hours and text normalization.
  const RELEASE = 185;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();