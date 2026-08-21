(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v174 reuses the already-processed agenda on warm starts when source data and local day are unchanged.
  const RELEASE = 174;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
