const CATEGORY = Object.freeze({
  exposiciones: { id: "exposiciones", label: "Exposiciones" },
  cine: { id: "cine", label: "Cine" },
  musica: { id: "musica", label: "Música" },
  teatro: { id: "teatro", label: "Teatro" },
  talleres: { id: "cursos-talleres", label: "Cursos y talleres" },
  ferias: { id: "ferias-gastronomia", label: "Ferias y gastronomía" },
  naturaleza: { id: "naturaleza-deportes", label: "Naturaleza y deportes" },
  otros: { id: "otros", label: "Otros panoramas" },
});

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function sourceCategory(event) {
  const source = event?.primary_category || event?.categories?.[0] || null;
  const label = String(source?.label || "").trim();
  const id = String(source?.id || fold(label).replace(/\s+/g, "-")).trim().toLocaleLowerCase("es");
  return { id, label };
}

function evidenceText(event) {
  return fold([
    event?.title,
    event?.description,
    event?.organizer,
    event?.source_name,
    ...(event?.tags || []),
  ].filter(Boolean).join(" "));
}

function inferCultureCategory(event) {
  const text = evidenceText(event);
  if (/\b(exposicion|exposiciones|muestra|muestras|museo|museos|galeria|fotografia|artes visuales|arte contemporaneo|instalacion artistica)\b/u.test(text)) return CATEGORY.exposiciones;
  if (/\b(cine|pelicula|peliculas|film|filme|audiovisual|documental|documentales|cortometraje|cortometrajes|largometraje|proyeccion)\b/u.test(text)) return CATEGORY.cine;
  if (/\b(musica|musical|concierto|conciertos|recital|recitales|jazz|coro|coral|orquesta|cantautor|cantautora|dj|sonidos)\b/u.test(text)) return CATEGORY.musica;
  if (/\b(teatro|teatral|obra|obras|danza|ballet|circo|escenicas|escenico|performance|funcion|espectaculo)\b/u.test(text)) return CATEGORY.teatro;
  if (/\b(taller|talleres|curso|cursos|clase|clases|formacion|seminario|laboratorio|workshop|capacitacion)\b/u.test(text)) return CATEGORY.talleres;
  if (/\b(feria|ferias|mercado|mercados|gastronomia|gastronomico|gastronomica|cocina|culinario|culinaria|comida|cerveza|vino|degustacion)\b/u.test(text)) return CATEGORY.ferias;
  if (/\b(naturaleza|natural|senderismo|trekking|excursion|excursiones|deporte|deportes|ciclismo|running|kayak|bicicleta|caminata|caminatas|aire libre)\b/u.test(text)) return CATEGORY.naturaleza;
  return CATEGORY.otros;
}

export function resolvePublicCategory(event) {
  const source = sourceCategory(event);
  if (source.id === "museos" || source.id === "exposiciones") return CATEGORY.exposiciones;
  if (source.id === "cultura" || fold(source.label) === "cultura") return inferCultureCategory(event);
  if (!source.id) return CATEGORY.otros;
  return { id: source.id, label: source.label || "Otros panoramas" };
}

export { CATEGORY, inferCultureCategory };
