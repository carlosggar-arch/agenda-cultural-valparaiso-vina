(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v192 consolidates semantic title recovery before public presentation.
  const RELEASE = 192;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
