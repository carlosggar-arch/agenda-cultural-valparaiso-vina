(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v129 keeps the fail-safe v128 startup and restores pure data transforms for
  // grouped cinema sessions plus the verified Museo Palacio Rioja exhibitions.
  const RELEASE = 129;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
