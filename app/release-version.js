(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v164 accelerates repeat startup while preserving fresh navigation and the complete offline shell.
  const RELEASE = 164;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();