(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v163 adds the canonical multi-city exhibition renderer and its visual-parity release gate on top of the v162 source/deploy hardening.
  const RELEASE = 163;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();