(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v195 separates semantic identity, occurrences and visual grouping.
  const RELEASE = 195;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
