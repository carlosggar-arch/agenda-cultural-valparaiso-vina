(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v203 gives the Google Maps arrow a subtle clickable pill and corrects vertical alignment on location rows.
  const RELEASE = 203;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
