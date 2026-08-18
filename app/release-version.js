(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v109 keeps the installed mobile action strip gapless with proportional icon tracks.
  const RELEASE = 109;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
