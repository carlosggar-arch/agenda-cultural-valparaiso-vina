(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v115 enables the shared schedule formatter in the installed app so verified
  // venue opening hours and corrected exhibition date ranges are rendered.
  const RELEASE = 115;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
