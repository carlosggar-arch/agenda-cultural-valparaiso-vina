(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v221 verifies owned event images end-to-end before publication is final.
  const RELEASE = 221;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
