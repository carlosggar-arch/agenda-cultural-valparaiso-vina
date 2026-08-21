(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v179 restores date-specific exhibition hours and removes duplicated venue text in Gijón.
  const RELEASE = 179;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();