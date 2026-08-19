(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v123 keeps museum hours and readable multi-event rows from v122, and restores
  // the verified “Decadencia” book presentation as a standalone Otros panoramas event.
  const RELEASE = 123;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
