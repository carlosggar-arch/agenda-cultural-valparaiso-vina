const sectionFilters = document.querySelector("[data-section-filters]");
const allowedFilters = new Set(["hoy", "fin-de-semana", "terminan-pronto", "gratis", "todos"]);

function ensureVisibleActiveFilter() {
  if (!sectionFilters) return;
  const buttons = [...sectionFilters.querySelectorAll("[data-section-filter]")];
  const active = buttons.find((button) => button.getAttribute("aria-pressed") === "true");
  if (active && allowedFilters.has(active.dataset.sectionFilter || "")) return;

  const fallback = sectionFilters.querySelector('[data-section-filter="todos"]');
  if (fallback && fallback.getAttribute("aria-pressed") !== "true") fallback.click();
}

if (sectionFilters) {
  const observer = new MutationObserver(() => queueMicrotask(ensureVisibleActiveFilter));
  observer.observe(sectionFilters, {
    subtree: true,
    attributes: true,
    attributeFilter: ["aria-pressed", "class"],
  });
  queueMicrotask(ensureVisibleActiveFilter);
}
