(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v165 keeps current main behavior while accelerating repeat startup with a release-scoped shell cache.
  const RELEASE = 165;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();