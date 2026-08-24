(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v217 preserves normalized official images and separates cached normalization
  // from timezone-aware runtime visibility.
  const RELEASE = 217;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
