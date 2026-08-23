(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v214 publishes representative-image quality and source-image preservation.
  const RELEASE = 214;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
