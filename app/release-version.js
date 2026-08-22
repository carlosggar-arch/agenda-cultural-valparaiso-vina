(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v199 adds discreet Google Maps navigation only for verified event locations.
  const RELEASE = 199;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();