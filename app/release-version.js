(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v188 consolidates visible agenda ordering under one shared authority.
  const RELEASE = 188;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
