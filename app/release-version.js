(() => {
  // Emergency rollback release. Restores the last known-good PWA runtime
  // while keeping current datasets intact, and forces a fresh service-worker cache.
  const RELEASE = 127;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
