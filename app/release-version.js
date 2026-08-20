(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v158 makes grouped MHNV opening hours resilient while preserving Fuentes access.
  const RELEASE = 158;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
