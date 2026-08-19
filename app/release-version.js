(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v134 keeps the v133 Gijon temporal fix and makes every date filter use the
  // same normalized event/session dataset as the core renderer.
  const RELEASE = 134;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();