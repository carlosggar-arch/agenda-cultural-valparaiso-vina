(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v170 serves cached navigation and datasets immediately, then refreshes them in the background.
  const RELEASE = 170;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
