const STYLE_ID = "exhibition-compact-styles";
const STYLE_HREF = "./exhibition-compact.css?v=20260818-compact1";
const grid = document.querySelector("[data-dated-grid]");
let queued = false;

function ensureStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const link = document.createElement("link");
  link.id = STYLE_ID;
  link.rel = "stylesheet";
  link.href = STYLE_HREF;
  document.head.append(link);
}

function validImageSources(card) {
  const seen = new Set();
  const sources = [];
  for (const img of card.querySelectorAll(".exhibition-collage-tile img")) {
    const src = String(img.currentSrc || img.src || "").trim();
    if (!src || seen.has(src)) continue;
    seen.add(src);
    sources.push(src);
  }
  return sources;
}

function applyRepresentativeFallback(card) {
  const sources = validImageSources(card);
  if (!sources.length) return;

  const missing = [...card.querySelectorAll(".grouped-exhibition-media.image-error")];
  missing.forEach((media, index) => {
    if (media.dataset.representativeFallback === "true") return;
    const src = sources[index % sources.length];
    if (!src) return;

    const img = document.createElement("img");
    img.src = src;
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";
    img.setAttribute("aria-hidden", "true");
    img.addEventListener("error", () => {
      img.remove();
      media.classList.add("image-error");
      media.classList.remove("is-representative-image");
      delete media.dataset.representativeFallback;
    }, { once: true });

    media.replaceChildren(img);
    media.classList.remove("image-error");
    media.classList.add("is-representative-image");
    media.dataset.representativeFallback = "true";
    media.title = "Imagen representativa de otra exposición del mismo recinto";
  });
}

function compactCards() {
  queued = false;
  if (!grid) return;
  for (const card of grid.querySelectorAll(".exhibition-venue-card")) {
    applyRepresentativeFallback(card);
  }
}

function queueCompact() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(compactCards);
}

ensureStyles();
queueCompact();

if (grid) {
  new MutationObserver(queueCompact).observe(grid, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class", "hidden", "src"],
  });
}
