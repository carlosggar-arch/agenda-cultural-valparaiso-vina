(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v128 structurally isolates startup from optional modules, removes data-path
  // fetch monkey patches and adds an independent safe-mode watchdog.
  const RELEASE = 128;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
