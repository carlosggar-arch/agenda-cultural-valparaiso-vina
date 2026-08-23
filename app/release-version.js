(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v212 keeps every dated event visible through its full local calendar day.
  const RELEASE = 212;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
