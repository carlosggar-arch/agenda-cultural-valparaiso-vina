(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v165 makes combined filters the sole owner of grouped-exhibition visibility,
  // so multi-exhibition cards cannot reappear under an unrelated category.
  const RELEASE = 165;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();