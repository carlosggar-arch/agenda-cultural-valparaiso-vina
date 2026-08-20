(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v154 stops forcing an immediate page reload when a new service worker takes
  // control. Updates remain automatic, but the refreshed shell is picked up on
  // the next normal navigation instead of causing a visible double load.
  const RELEASE = 154;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
