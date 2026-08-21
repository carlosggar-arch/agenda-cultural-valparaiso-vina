(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v171 yields after the first render so mobile input and paint are not blocked by secondary enrichers.
  const RELEASE = 171;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
