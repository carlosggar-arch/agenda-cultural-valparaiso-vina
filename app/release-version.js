(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v133 keeps Gijon on the stable core renderer and prevents the secondary
  // temporal-confidence guard from hiding valid combined-filter results.
  const RELEASE = 133;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
