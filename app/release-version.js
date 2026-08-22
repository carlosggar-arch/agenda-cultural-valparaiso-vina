(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v196 consolidates card, group, detail and guard image decisions under one resolver.
  const RELEASE = 196;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
