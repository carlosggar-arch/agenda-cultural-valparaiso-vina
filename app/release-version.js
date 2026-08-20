(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v156 preserves the Fuentes access across delayed footer remounts and adds
  // the official MHNV visit hours to multi-day museum exhibition cards.
  const RELEASE = 156;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
