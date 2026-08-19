(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v124 keeps museum hours/readable multi-event rows and aligns the restored
  // “Decadencia” book presentation with the current official municipal schedule.
  const RELEASE = 124;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
