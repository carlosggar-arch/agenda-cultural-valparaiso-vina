(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v172 lets the browser paint before secondary presentation work on mobile.
  const RELEASE = 172;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
