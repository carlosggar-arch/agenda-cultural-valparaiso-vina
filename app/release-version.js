(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v213 reloads an open installed App when a newer runtime takes control.
  const RELEASE = 213;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
