function removeLegacyTemporalUi() {
  document.querySelectorAll("[data-temporal-priority], style[data-temporal-priority-styles], .temporal-urgency-badge")
    .forEach((node) => node.remove());
}

// C2: this module is intentionally limited to retiring the old temporal UI.
// Event-card visibility, including confidence-based temporal suppression, is
// owned by combined-filters.js through visibility-owner-core.mjs.
function cleanupLegacyTemporalUi() {
  removeLegacyTemporalUi();
}

cleanupLegacyTemporalUi();
for (const eventName of [
  "vivamos:agenda-data-ready",
  "vivamos:agenda-rendered",
  "vivamos:core-ready",
]) {
  window.addEventListener(eventName, cleanupLegacyTemporalUi);
}
