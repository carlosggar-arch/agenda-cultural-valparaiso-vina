import "./category-normalizer.js?v=20260818-categories3";

const filtersReady = import("./combined-filters.js?v=20260818-public-taxonomy1");
filtersReady
  .then(() => import("./approved-event-integrity.js?v=20260818-integrity1"))
  .catch((error) => console.error("¡Vivamos!: secondary filter layer failed", error));
