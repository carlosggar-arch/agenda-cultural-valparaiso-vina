import "./category-normalizer.js?v=20260818-categories3";

// Secondary filtering must never block or mutate-loop the base agenda renderer.
// Approved-event integrity is enforced in CI; the browser only applies filters.
import("./combined-filters.js?v=20260818-public-taxonomy1")
  .catch((error) => console.error("¡Vivamos!: secondary filter layer failed", error));
