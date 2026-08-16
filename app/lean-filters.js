const sectionFilters = document.querySelector("[data-section-filters]");
const discovery = document.querySelector("[data-discovery]");
const allowedFilters = new Set(["hoy", "fin-de-semana", "terminan-pronto", "gratis", "todos"]);

function ensureVisibleActiveFilter() {
  if (!sectionFilters || discovery?.hidden) return;
  const buttons = [...sectionFilters.querySelectorAll("[data-section-filter]")];
  const active = buttons.find((button) => button.getAttribute("aria-pressed") === "true");
  if (active && allowedFilters.has(active.dataset.sectionFilter || "")) return;

  const fallback = sectionFilters.querySelector('[data-section-filter="todos"]');
  if (fallback && fallback.getAttribute("aria-pressed") !== "true") fallback.click();
}

if (discovery) {
  const observer = new MutationObserver(() => {
    if (!discovery.hidden) queueMicrotask(ensureVisibleActiveFilter);
  });
  observer.observe(discovery, { attributes: true, attributeFilter: ["hidden"] });
  if (!discovery.hidden) queueMicrotask(ensureVisibleActiveFilter);
}
