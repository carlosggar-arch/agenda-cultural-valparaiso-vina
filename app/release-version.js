(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v111 hotfixes an infinite DOM observer loop introduced while removing likes.
  const RELEASE = 111;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
