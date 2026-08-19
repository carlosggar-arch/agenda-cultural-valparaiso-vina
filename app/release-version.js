(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v126 removes the two recently added startup fetch/DOM interception layers
  // from the critical path after production freezes persisted in WEB and APP.
  const RELEASE = 126;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
