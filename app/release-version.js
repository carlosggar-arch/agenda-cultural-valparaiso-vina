(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v155 makes the Fuentes access deterministic: the footer keeps a direct
  // catalogue link even if the richer in-page source module cannot initialize.
  const RELEASE = 155;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
