(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v210 enforces the exact 25 px Maps control through the accessibility cascade.
  const RELEASE = 210;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
