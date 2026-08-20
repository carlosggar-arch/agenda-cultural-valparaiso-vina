(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v161 focuses multi-session cards on the sessions of the current local day.
  const RELEASE = 161;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
