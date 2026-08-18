const GENERIC_EXHIBITION_FALLBACK = new URL("../assets/categoria-exposiciones.jpg", import.meta.url).href;
const grids = [...document.querySelectorAll(".event-grid")];
let timer = null;

function ensureFallbackImage(container, alt) {
  if (!container || container.querySelector("img")) return;
  const img = document.createElement("img");
  img.src = GENERIC_EXHIBITION_FALLBACK;
  img.alt = alt;
  img.loading = "lazy";
  img.decoding = "async";
  container.replaceChildren(img);
  container.classList.remove("image-error");
}

function patchCard(card) {
  if (!(card instanceof HTMLElement) || !card.classList.contains("exhibition-venue-card")) return;
  if (card.dataset.safeCompactPatched === "true") return;

  const collage = card.querySelector("[data-exhibition-collage]");
  if (collage && !collage.querySelector("img")) {
    collage.replaceChildren();
    const tile = document.createElement("div");
    tile.className = "exhibition-collage-tile is-fallback-image";
    ensureFallbackImage(tile, "Imagen representativa de exposiciones");
    collage.append(tile);
    collage.dataset.count = "1";
  }

  for (const row of card.querySelectorAll("[data-grouped-event-id]")) {
    const media = row.querySelector(".grouped-exhibition-media");
    if (!media) continue;
    const current = media.querySelector("img");
    if (current) {
      current.addEventListener("error", () => {
        media.replaceChildren();
        ensureFallbackImage(media, "");
      }, { once: true });
    } else {
      ensureFallbackImage(media, "");
    }
  }

  card.dataset.safeCompactPatched = "true";
}

function patchAll() {
  timer = null;
  for (const grid of grids) {
    for (const card of grid.querySelectorAll(".exhibition-venue-card")) patchCard(card);
  }
}

function schedulePatch(delay = 40) {
  if (timer) clearTimeout(timer);
  timer = setTimeout(patchAll, delay);
}

for (const grid of grids) {
  new MutationObserver(schedulePatch).observe(grid, { childList: true, subtree: true });
}

window.addEventListener("pageshow", () => schedulePatch(0), { passive: true });
document.addEventListener("click", () => schedulePatch(80), { passive: true });
schedulePatch(0);
