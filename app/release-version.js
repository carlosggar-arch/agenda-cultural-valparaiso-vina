(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v157 renders the official MHNV visit hours inside grouped exhibition cards.
  const RELEASE = 157;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
