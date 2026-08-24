function defaultAlt(event, kind) {
  if (kind === "representative") {
    const venue = String(event?.location?.venue || "el recinto").trim();
    return `Imagen representativa de ${venue}`;
  }
  if (kind === "generated-fallback") {
    return `Imagen editorial generada para ${String(event?.title || "la actividad").trim()}`;
  }
  return String(event?.image?.alt || event?.title || "Imagen de la actividad").trim();
}

/**
 * Canonical DOM renderer for event images on WEB and App surfaces.
 * Image selection remains owned by image-resolver-core; this function owns
 * the resulting <img> contract so both surfaces expose identical evidence.
 */
export function createEventImageElement(event, {
  url,
  kind = "relevant",
  documentRef = document,
  className = "event-card-photo",
  loading = "lazy",
  decoding = "async",
  onError = null,
} = {}) {
  if (!url) throw new TypeError("createEventImageElement requires a resolved URL");
  const image = documentRef.createElement("img");
  image.className = className;
  image.src = String(url);
  image.alt = defaultAlt(event, kind);
  image.loading = loading;
  image.decoding = decoding;
  image.dataset.eventImage = kind;
  image.dataset.eventImageId = String(event?.id || "").trim();
  if (typeof onError === "function") image.addEventListener("error", onError, { once: true });
  return image;
}
