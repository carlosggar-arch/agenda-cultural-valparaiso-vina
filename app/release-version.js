(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v126 moves data normalization into an explicit resilient pipeline, starts
  // the core before optional UI modules, and adds an independent safe-mode watchdog.
  const RELEASE = 126;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
