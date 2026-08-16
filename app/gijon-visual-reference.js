const VISUAL_REFERENCE = Object.freeze({
  city: "gijon",
  title: "Explorar actividades en Gijón",
  copy: "Interfaz visual oficial del Ayuntamiento para consultar programas, actividades e inscripciones.",
  url: "https://www.gijon.es/app/actividades/oferta",
});

function buildVisualReference() {
  const card = document.createElement("article");
  card.className = "source-card source-card--visual-reference";
  card.dataset.gijonVisualReference = "true";

  const heading = document.createElement("div");
  heading.className = "source-card-heading";

  const title = document.createElement("strong");
  title.textContent = VISUAL_REFERENCE.title;
  heading.append(title);

  const badge = document.createElement("span");
  badge.className = "source-official-badge";
  badge.textContent = "Oficial";
  heading.append(badge);

  const copy = document.createElement("small");
  copy.textContent = VISUAL_REFERENCE.copy;

  const link = document.createElement("a");
  link.href = VISUAL_REFERENCE.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Abrir agenda visual →";

  card.append(heading, copy, link);
  return card;
}

function syncVisualReference() {
  const grid = document.querySelector("[data-sources-grid]");
  if (!grid) return;

  const existing = grid.querySelector("[data-gijon-visual-reference]");
  const isGijon = document.documentElement.dataset.city === VISUAL_REFERENCE.city;

  if (!isGijon) {
    existing?.remove();
    return;
  }

  if (!existing && grid.children.length > 0) {
    grid.prepend(buildVisualReference());
  }
}

const grid = document.querySelector("[data-sources-grid]");
if (grid) {
  new MutationObserver(syncVisualReference).observe(grid, { childList: true });
}
new MutationObserver(syncVisualReference).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-city"],
});

syncVisualReference();
