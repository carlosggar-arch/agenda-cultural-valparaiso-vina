const STORAGE_KEY = "agenda-cultural-city";

const CATEGORY_PHOTOS = Object.freeze([
  { markers: ["cine"], src: "../assets/categoria-cine.jpg" },
  { markers: ["música", "musica"], src: "../assets/categoria-musica.jpg" },
  { markers: ["teatro", "artes escénicas", "artes escenicas", "danza"], src: "../assets/categoria-teatro.jpg" },
  { markers: ["exposiciones", "exposición", "exposicion", "museos", "museo", "artes visuales"], src: "../assets/categoria-exposiciones.jpg" },
  { markers: ["curso", "taller", "formación", "formacion"], src: "../assets/categoria-talleres.jpg" },
  { markers: ["deporte", "bienestar"], src: "../assets/categoria-deportes.jpg" },
  { markers: ["gastronomía", "gastronomia", "feria"], src: "../assets/categoria-gastronomia.jpg" },
  { markers: ["naturaleza", "montaña", "montana", "caminata"], src: "../assets/categoria-naturaleza.jpg" },
]);

function activeCity() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function normalize(value) {
  return String(value || "").trim().toLocaleLowerCase("es");
}

function categoryPhoto(label) {
  const normalized = normalize(label);
  const match = CATEGORY_PHOTOS.find(({ markers }) => markers.some((marker) => normalized.includes(marker)));
  return match?.src || "../assets/categoria-cultura.jpg";
}

function upgradePlaceholder(media) {
  if (!(media instanceof HTMLElement) || media.dataset.categoryPhotoApplied === "true") return;
  if (activeCity() !== "valparaiso") return;

  const label = media.querySelector(".event-card-placeholder-label")?.textContent?.trim() || "Cultura";
  const image = document.createElement("img");
  image.className = "event-card-photo";
  image.src = categoryPhoto(label);
  image.alt = `Imagen representativa de la categoría ${label}`;
  image.loading = "lazy";
  image.decoding = "async";
  image.dataset.imageKind = "category-fallback";

  image.addEventListener("error", () => {
    media.dataset.categoryPhotoApplied = "failed";
  }, { once: true });

  media.replaceChildren(image);
  media.classList.remove("event-card-media--placeholder");
  media.dataset.categoryPhotoApplied = "true";
}

function scan() {
  if (activeCity() !== "valparaiso") return;
  document.querySelectorAll(".event-card-media--placeholder").forEach(upgradePlaceholder);
}

const observer = new MutationObserver(scan);
observer.observe(document.body, { childList: true, subtree: true });
scan();
