(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v165 keeps fresh navigation/data while avoiding redundant shell revalidation on warm startup.
  const RELEASE = 165;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();