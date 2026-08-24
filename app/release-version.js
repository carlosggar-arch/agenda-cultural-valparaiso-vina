(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v219 resolves repository-owned event art identically from WEB and App.
  const RELEASE = 219;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
