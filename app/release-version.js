(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v216 normalizes malformed official image metadata across every city.
  const RELEASE = 216;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
