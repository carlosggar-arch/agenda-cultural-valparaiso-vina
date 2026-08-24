(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v222 verifies owned event images end-to-end without competing WEB mutation owners.
  const RELEASE = 222;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
