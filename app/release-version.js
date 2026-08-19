(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v129 keeps city filter state isolated and fails open to the already-rendered
  // agenda if the secondary filter dataset fetch is unavailable.
  const RELEASE = 129;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
