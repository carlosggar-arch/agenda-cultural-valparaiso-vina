(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v165 combines registration reminders with deterministic generation, canonical venue identity and generated offline shell assets.
  const RELEASE = 165;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
