(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v197 makes iOS install intent explicit and moves mobile install metadata into the initial document.
  const RELEASE = 197;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
