(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v184 consolidates canonical event sessions, venue hours and date-aware display.
  const RELEASE = 184;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();