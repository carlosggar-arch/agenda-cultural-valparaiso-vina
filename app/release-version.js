(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v206 adds the guided four-step iPhone install flow opened by the shared QR.
  const RELEASE = 206;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
