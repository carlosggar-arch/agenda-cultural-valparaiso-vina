(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v114 prevents any legacy UI from painting before the current installed-app
  // interface is ready, using a head-loaded branded startup guard.
  const RELEASE = 114;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
