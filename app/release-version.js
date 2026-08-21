(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v167 preserves the generated-shell architecture and adds the validated faster-startup cache strategy.
  const RELEASE = 167;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
