const baseReady = (async () => {
  await import("./category-normalizer.js?v=20260818-categories3");
  await import("./app-core.js?v=20260818-exhibitions1");
  await import("./exhibition-venue-grouping.js?v=20260818-venuegroup1");
  await import("./exhibition-gallery.js?v=20260818-gallery2");
  await import("./exhibition-compact-loader.js?v=20260818-compact9");
  await import("./presentation-normalizer.js?v=20260818-presentation3");
  await import("./footer-credit.js?v=20260818-footer1");
})();

globalThis.__vivamosAppBaseReady = baseReady;
await baseReady;
