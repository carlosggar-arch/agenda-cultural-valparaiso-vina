const CATEGORY = Object.freeze({
  exposiciones: { id: "exposiciones", label: "Exposiciones y museos" },
  cine: { id: "cine", label: "Cine" },
  musica: { id: "musica", label: "Música" },
  teatro: { id: "teatro", label: "Teatro" },
  talleres: { id: "cursos-talleres", label: "Cursos y talleres" },
  ferias: { id: "ferias-gastronomia", label: "Ferias y gastronomía" },
  naturaleza: { id: "naturaleza-deportes", label: "Naturaleza y deportes" },
  otros: { id: "otros", label: "Otros panoramas" },
});

const SOURCE_ALIASES = new Map([
  ["museos", CATEGORY.exposiciones],
  ["museo", CATEGORY.exposiciones],
  ["exposiciones", CATEGORY.exposiciones],
  ["exposicion", CATEGORY.exposiciones],
  ["ferias", CATEGORY.ferias],
  ["feria", CATEGORY.ferias],
  ["gastronomia", CATEGORY.ferias],
  ["ferias-gastronomia", CATEGORY.ferias],
  ["naturaleza", CATEGORY.naturaleza],
  ["naturaleza-montana", CATEGORY.naturaleza],
  ["deportes", CATEGORY.naturaleza],
  ["naturaleza-deportes", CATEGORY.naturaleza],
  ["cursos-talleres", CATEGORY.talleres],
  ["talleres", CATEGORY.talleres],
  ["musica", CATEGORY.musica],
  ["cine", CATEGORY.cine],
  ["teatro", CATEGORY.teatro],
  ["otros", CATEGORY.otros],
]);

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

function explicitTitleCategory(event) {
  const title = fold(event?.title);
  if (!title) return null;
  if (/\b(exposicion|exposiciones|muestra|muestras|visita guiada exposicion|visita guiada muestra)\b/u.test(title)) return CATEGORY.exposiciones;
  if (/\b(cine|pelicula|film|filme|documental|cortometraje|largometraje|proyeccion)\b/u.test(title)) return CATEGORY.cine;
  if (/\b(concierto|recital|jazz|coro|coral|orquesta|musica)\b/u.test(title)) return CATEGORY.musica;
  if (/\b(teatro|danza|ballet|circo|performance|funcion|espectaculo)\b/u.test(title)) return CATEGORY.teatro;
  if (/\b(taller|curso|clase|seminario|laboratorio|workshop|capacitacion)\b/u.test(title)) return CATEGORY.talleres;
  if (/\b(presentacion de?l? libro|presentacion libro|lanzamiento de?l? libro|lectura|poesia|encuentro literario|conversatorio literario)\b/u.test(title)) return CATEGORY.otros;
  return null;
}

function inferCultureCategory(event) {
  const explicit = explicitTitleCategory(event);
  if (explicit) return explicit;

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

export function resolveRootPublicCategory(event) {
  const source = sourceCategory(event);
  const aliased = SOURCE_ALIASES.get(source.id);
  if (aliased) return aliased;
  if (source.id === "cultura" || fold(source.label) === "cultura" || !source.id) return inferCultureCategory(event);

  // La WEB publica sólo la misma taxonomía estable de APP. Si una fuente trae
  // una etiqueta no canónica, la evidencia del evento decide la categoría;
  // si no hay evidencia suficiente, cae en Otros panoramas.
  return inferCultureCategory(event);
}

export { CATEGORY, explicitTitleCategory, inferCultureCategory };
