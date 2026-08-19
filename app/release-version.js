(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v117 forces the live app to reload the versioned schedule modules so the
  // corrected paired-range formatter is visible instead of stale cached code.
  const RELEASE = 117;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
