(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v112 redistributes the installed mobile action strip across six controls after removing likes.
  const RELEASE = 112;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
