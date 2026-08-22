(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v186 clarifies exhibition visit hours and surfaces verified event-specific official sources.
  const RELEASE = 186;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
