(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v194 routes city corroborations through canonical source evidence.
  const RELEASE = 194;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
