(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v177 reduces repeated JavaScript and DOM work in initial and filtered renders.
  const RELEASE = 177;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
