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

const GENERIC_PROVIDER_HOSTS = /(^|\.)(passline\.com|eventrid\.cl|ticketplus\.(cl|com)|ticketmaster\.cl|puntoticket\.com|ticketpro\.(cl|com|net)|tickets\.cl|ticketera\.cl|ticketfacil\.cl|portaltickets\.cl|goignis\.cl)$/i;
const GENERIC_PROVIDER_PATH = /(?:^|\/)(?:assets?\/(?:img|images?)\/)?(?:icon|logo|favicon|placeholder|default|no[-_]?image|sin[-_]?imagen)(?:[-_.\/]|$)/i;

// Curated correction for the duplicated film listing. The source image below is
// the event-specific artwork already used by the same film in this agenda.
const EVENT_IMAGE_OVERRIDES = Object.freeze({
  "la odisea": "https://www.passline.com/imagenes/eventos/la-odisea-2026-cine-arte-vina-del-mar-544722-rec.jpg",
});

function normalize(value) {
  return String(value || "").trim().toLocaleLowerCase("es");
}

function eventKey(value) {
  return normalize(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\b(?:19|20)\d{2}\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function categoryPhoto(label) {
  const normalized = normalize(label);
  const match = CATEGORY_PHOTOS.find(({ markers }) => markers.some((marker) => normalized.includes(marker)));
  return match?.src || "../assets/categoria-cultura.jpg";
}

function isGenericProviderImage(value) {
  if (!value) return false;
  try {
    const url = new URL(String(value), window.location.href);
    const host = url.hostname.replace(/^www\./i, "");
    if (!GENERIC_PROVIDER_HOSTS.test(host)) return false;
    return GENERIC_PROVIDER_PATH.test(decodeURIComponent(url.pathname).toLocaleLowerCase("es"));
  } catch {
    return false;
  }
}

function setMediaImage(media, url) {
  if (!(media instanceof HTMLElement) || !url) return;
  media.style.setProperty("--event-image", `url("${String(url).replaceAll('"', "%22")}")`);
}

function titleForImage(image) {
  const card = image.closest(".event-card");
  if (card) return card.querySelector("h4")?.textContent?.trim() || "";
  const detail = image.closest(".event-detail-panel");
  return detail?.querySelector(".event-detail-title")?.textContent?.trim() || "";
}

function repairGenericProviderImage(image) {
  if (!(image instanceof HTMLImageElement)) return;
  const requestedSrc = image.getAttribute("src") || image.src;
  if (!isGenericProviderImage(requestedSrc)) return;

  const title = titleForImage(image);
  const override = EVENT_IMAGE_OVERRIDES[eventKey(title)];
  const media = image.closest(".event-card-media, .event-detail-media");

  if (override) {
    image.src = override;
    image.alt = title || image.alt || "Imagen de la actividad";
    image.dataset.imageKind = "event-image-corrected";
    setMediaImage(media, override);
    return;
  }

  // Never show a provider logo/icon as if it were event artwork. Cards without
  // a trustworthy specific image fall back to the category image instead.
  const card = image.closest(".event-card");
  if (card) {
    const label = card.querySelector(".meta")?.textContent?.trim() || "Cultura";
    const fallback = categoryPhoto(label);
    image.src = fallback;
    image.alt = `Imagen representativa de la categoría ${label}`;
    image.dataset.imageKind = "category-fallback";
    setMediaImage(media, fallback);
    return;
  }

  // In the detail dialog, prefer no artwork over misleading provider branding.
  const detailMedia = image.closest(".event-detail-media");
  if (detailMedia) {
    const panel = detailMedia.closest(".event-detail-panel");
    detailMedia.remove();
    panel?.classList.add("event-detail-panel--no-media");
  }
}

function upgradePlaceholder(media) {
  if (!(media instanceof HTMLElement) || media.dataset.categoryPhotoApplied === "true") return;

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
  document.querySelectorAll('img[data-event-image="relevant"]').forEach(repairGenericProviderImage);
  document.querySelectorAll(".event-card-media--placeholder").forEach(upgradePlaceholder);
}

const observer = new MutationObserver(scan);
observer.observe(document.body, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["src"],
});
scan();
