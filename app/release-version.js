(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v215 preserves verified official images regardless of descriptive filenames.
  const RELEASE = 215;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
