const GIJON_MUSEUM_DIRECTORY = "https://opendata.gijon.es/descargar.php?id=790&tipo=XHTML";
const GIJON_CENTRE_DIRECTORY = "https://opendata.gijon.es/descargar.php?id=746&tipo=XHTML";
const REVILLAGIGEDO_HOURS = "https://www.turismoasturias.es/es/descubre/cultura/museos-y-espacios-culturales/otros-espacios/palacio-de-revillagigedo";

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’‘`]/g, "'")
    .toLocaleLowerCase("es")
    .replace(/\s+/g, " ")
    .trim();
}

const HOURS = new Map([
  [fold("Muséu del Pueblu d'Asturies"), {
    display: "Abr–sep · mar–vie 10:00–19:00 · sáb, dom y festivos 10:30–19:00 · lunes cerrado. Oct–mar · mar–vie 09:30–18:30 · sáb, dom y festivos 10:00–18:30.",
    source: GIJON_MUSEUM_DIRECTORY,
  }],
  [fold("Museo Nicanor Piñole"), {
    display: "Mar–vie 09:30–14:00 y 17:00–19:30 · sáb, dom y festivos 10:00–14:00 y 17:00–19:30 · lunes cerrado.",
    source: GIJON_MUSEUM_DIRECTORY,
  }],
  [fold("Museo Casa Natal de Jovellanos"), {
    display: "Mar–vie 09:30–14:00 y 17:00–19:30 · sáb, dom y festivos 10:00–14:00 y 17:00–19:30 · lunes cerrado.",
    source: GIJON_MUSEUM_DIRECTORY,
  }],
  [fold("Museo Villa Romana de Veranes"), {
    display: "16 jun–15 sep · mar–dom y festivos 10:30–19:00 · lunes cerrado. 16 sep–15 jun · mar–dom y festivos 10:00–15:00 · lunes cerrado.",
    source: GIJON_MUSEUM_DIRECTORY,
  }],
  [fold("Museo Termas Romanas de Campo Valdés"), {
    display: "Mar–vie 09:30–14:00 y 17:00–19:30 · sáb, dom y festivos 10:00–14:00 y 17:00–19:30 · lunes cerrado.",
    source: GIJON_MUSEUM_DIRECTORY,
  }],
  [fold("Museo del Ferrocarril de Asturias"), {
    display: "Abr–sep · mar–vie 10:00–19:00 · sáb, dom y festivos 10:30–19:00 · lunes cerrado. Oct–mar · mar–vie 09:30–18:30 · sáb, dom y festivos 10:00–18:30.",
    source: GIJON_MUSEUM_DIRECTORY,
  }],
  [fold("Museo de la Ciudadela de Celestino Solar"), {
    display: "Abr–sep · mar–dom 11:00–19:00 · lunes cerrado. Oct–mar · mar–dom 11:30–18:30 · lunes cerrado.",
    source: GIJON_MUSEUM_DIRECTORY,
  }],
  [fold("Museo Barjola"), {
    display: "Mar–sáb 11:30–13:30 y 17:00–20:00 · dom y festivos 12:00–14:00 · lunes cerrado.",
    source: GIJON_MUSEUM_DIRECTORY,
  }],
  [fold("Jardín Botánico Atlántico de Gijón"), {
    display: "Ene, feb, oct–dic · 10:00–18:00 · marzo 10:00–19:00 · abril y septiembre 10:00–20:00 · mayo–agosto 10:00–21:00. Habitualmente mar–dom; lunes también abre en julio y agosto.",
    source: GIJON_MUSEUM_DIRECTORY,
  }],
  [fold("Centro de Cultura Antiguo Instituto"), {
    display: "Lun–vie 09:00–21:00 · sáb 11:00–14:00 y 16:00–21:00 · dom y festivos 11:00–14:00.",
    source: GIJON_CENTRE_DIRECTORY,
  }],
  [fold("Centro Municipal Integrado L'Arena"), {
    display: "Lun–vie 08:00–21:30.",
    source: GIJON_CENTRE_DIRECTORY,
  }],
  [fold("Centro Municipal Integrado El Coto"), {
    display: "Lun–vie 08:00–21:30.",
    source: GIJON_CENTRE_DIRECTORY,
  }],
  [fold("Centro Municipal Integrado Pumarín Gijón Sur"), {
    display: "Lun–sáb 08:00–21:30 · dom 08:00–15:00.",
    source: GIJON_CENTRE_DIRECTORY,
  }],
  [fold("Centro Municipal Integrado El Llano"), {
    display: "Lun–sáb 08:00–21:30 · dom 08:00–15:00.",
    source: GIJON_CENTRE_DIRECTORY,
  }],
  [fold("Centro Municipal Integrado Ateneo de La Calzada"), {
    display: "Lun–sáb 08:00–21:30.",
    source: GIJON_CENTRE_DIRECTORY,
  }],
  [fold("Palacio de Revillagigedo de la Fundación Cajastur"), {
    display: "Jul–ago · mar–sáb 11:00–13:30 y 16:00–21:00 · dom y festivos 12:00–14:30 · lunes cerrado. Resto del año · mar–sáb 11:30–13:30 y 17:00–20:00 · dom y festivos 12:00–14:00.",
    source: REVILLAGIGEDO_HOURS,
  }],
]);

const EVENT_LOCATION_OVERRIDES = new Map([
  ["https://www.gijon.es/la-escuela-de-gijon-la-ciudad-como-motivo-exposicion", {
    venue_id: "3224",
    venue: "Centro de Cultura Antiguo Instituto",
    address: "C/Jovellanos, 21",
    verification: "verified_event_venue_correction",
  }],
]);

function explicitRealTime(value) {
  const match = String(value || "").match(/T([0-2]\d:[0-5]\d)/);
  if (!match) return false;
  return !["00:00", "23:59"].includes(match[1]);
}

function hasExplicitEventTime(schedule) {
  if (explicitRealTime(schedule?.start)) return true;
  if (Array.isArray(schedule?.occurrences) && schedule.occurrences.some((item) => explicitRealTime(item?.start))) return true;
  const display = String(schedule?.display_text || "");
  const times = [...display.matchAll(/(?:^|[^\d])([0-2]\d:[0-5]\d)/g)].map((match) => match[1]);
  return times.some((time) => !["00:00", "23:59"].includes(time));
}

function cleanPlaceholderDisplay(schedule) {
  const display = String(schedule?.display_text || "").trim();
  if (!display) return display;
  return display
    .replace(/\s*·\s*(?:00:00|23:59)(?=\s*$)/, "")
    .replace(/\s+/g, " ")
    .trim();
}

function officialEventUrl(event) {
  return String(event?.links?.official || event?.links?.source || "").replace(/\/$/, "");
}

export function gijonLocationForEvent(event) {
  const location = { ...(event?.location || {}) };
  const override = EVENT_LOCATION_OVERRIDES.get(officialEventUrl(event));
  if (!override) return location;
  return { ...location, ...override };
}

export function scheduleForGijonEvent(event) {
  const schedule = event?.schedule;
  if (!schedule || typeof schedule !== "object" || hasExplicitEventTime(schedule)) return schedule;

  const next = { ...schedule, display_text: cleanPlaceholderDisplay(schedule) };
  const location = gijonLocationForEvent(event);
  const venue = HOURS.get(fold(location?.venue));
  if (!venue) return next;

  next.opening_hours = {
    mode: "venue",
    display_text: venue.display,
    source_name: "Horario oficial del recinto",
    source_url: venue.source,
    verified_at: "2026-08-17",
  };
  next.hours_confidence = "official_venue_directory";
  return next;
}

export function gijonVenueHours(event) {
  const location = gijonLocationForEvent(event);
  return HOURS.get(fold(location?.venue)) || null;
}
