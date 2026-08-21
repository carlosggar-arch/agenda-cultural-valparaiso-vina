(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v173 reuses the already-processed agenda on warm starts when source data and local day are unchanged.
  const RELEASE = 173;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
