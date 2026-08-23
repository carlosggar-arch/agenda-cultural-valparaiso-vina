(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v208 makes WEB and APP consume one canonical dataset and selection authority.
  const RELEASE = 208;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
