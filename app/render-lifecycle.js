const GRID_SELECTORS = [
  "[data-dated-grid]",
  "[data-program-grid]",
  "[data-flexible-grid]",
];

let queued = false;
let renderRevision = 0;
let pendingReason = "startup";

function currentCityId() {
  return String(document.documentElement.dataset.city || "").trim();
}

function visibleCardCount(root) {
  if (!root) return 0;
  return [...root.children].filter((node) => node instanceof HTMLElement && node.classList.contains("event-card") && !node.hidden).length;
}

function emitRenderLifecycle() {
  queued = false;
  const roots = GRID_SELECTORS.map((selector) => document.querySelector(selector));
  window.dispatchEvent(new CustomEvent("vivamos:agenda-rendered", {
    detail: {
      cityId: currentCityId(),
      revision: ++renderRevision,
      reason: pendingReason,
      directCards: roots.reduce((total, root) => total + visibleCardCount(root), 0),
    },
  }));
  pendingReason = "dom-update";
}

export function notifyAgendaRendered(reason = "explicit") {
  pendingReason = reason;
  if (queued) return;
  queued = true;
  queueMicrotask(emitRenderLifecycle);
}

// One bounded observer replaces the former stack of body-wide subtree observers.
// It watches only direct card-list membership; text, image and descendant changes
// cannot recursively retrigger the presentation pipeline.
const observer = new MutationObserver((records) => {
  if (records.some((record) => record.type === "childList" && (record.addedNodes.length || record.removedNodes.length))) {
    notifyAgendaRendered("grid-membership");
  }
});

for (const selector of GRID_SELECTORS) {
  const root = document.querySelector(selector);
  if (root) observer.observe(root, { childList: true });
}

window.addEventListener("vivamos:agenda-data-ready", () => notifyAgendaRendered("data-ready"));
window.addEventListener("pageshow", () => notifyAgendaRendered("pageshow"), { passive: true });
notifyAgendaRendered("startup");
