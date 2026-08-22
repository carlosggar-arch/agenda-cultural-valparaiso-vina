(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v191 consolidates public category aliases under the shared taxonomy.
  const RELEASE = 191;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
