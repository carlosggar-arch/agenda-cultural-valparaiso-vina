(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v160 restores grouped exhibition integrity and structural text/program guards.
  const RELEASE = 160;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
