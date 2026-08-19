(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v132 keeps Gijon on the stable core renderer and defers observer-heavy card
  // presentation layers that can freeze the page after the initial render.
  const RELEASE = 132;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
