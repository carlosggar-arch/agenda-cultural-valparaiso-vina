import { gijonVenueHours } from "./gijon-venue-hours.js";

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’‘`]/g, "'")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9']+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function venueKey(value) {
  return fold(value)
    .replace(/^(?:museo|museu|museum)\s+/, "")
    .trim();
}

const VALPARAISO_VENUE_HOURS = new Map();

function registerValparaiso(names, display, source, verifiedAt = "2026-08-19") {
  const record = Object.freeze({ display, source, verified_at: verifiedAt });
  for (const name of names) VALPARAISO_VENUE_HOURS.set(venueKey(name), record);
}

registerValparaiso(
  ["Museo de Historia Natural de Valparaíso"],
  "Mar–vie 10:00–18:00 · sáb 11:00–16:00 · dom, lun y festivos cerrado.",
  "https://www.mhnv.gob.cl/planifica-tu-visita",
);
registerValparaiso(
  ["Museo Palacio Rioja", "Palacio Rioja"],
  "Mar–dom 10:00–17:30.",
  "https://visitavina.munivina.cl/museo-palacio-rioja/",
);
registerValparaiso(
  ["Museo Palacio Vergara", "Palacio Vergara"],
  "Mar–dom 10:00–17:30.",
  "https://visitavina.munivina.cl/museo-palacio-vergara/",
);
registerValparaiso(
  ["Museo Baburizza", "Palacio Baburizza"],
  "Mar–dom 10:00–18:00.",
  "https://www.museobaburizza.cl/visita/",
);
registerValparaiso(
  ["Museo Fonck"],
  "Lun 10:00–14:00 y 15:00–18:00 · mar–sáb 10:00–18:00 · dom y festivos 10:00–14:00.",
  "https://museofonck.cl/new_site/index.php/horario-y-valores",
);
registerValparaiso(
  ["Museo Artequin", "Museo Artequín", "Artequin Viña del Mar", "Artequín Viña del Mar"],
  "Mar–vie 09:00–17:00 · sáb–dom 10:00–18:00.",
  "https://visitavina.munivina.cl/museos-y-palacios/artequin-vina-del-mar/",
);
registerValparaiso(
  ["Museo Marítimo Nacional", "Museo Maritimo Nacional"],
  "Lun–dom 10:00–18:00 · último ingreso 17:30.",
  "https://museomaritimo.cl/horarios/",
);

function explicitHours(event) {
  const schedule = event?.schedule || {};
  const opening = schedule?.opening_hours || {};
  const candidates = [
    opening.display_text,
    schedule.venue_opening_hours,
    schedule.visit_hours,
    event?.location?.opening_hours,
  ];
  const display = candidates.map((item) => String(item || "").replace(/\s+/g, " ").trim()).find(Boolean);
  if (!display) return null;
  return {
    display,
    source: String(opening.source_url || schedule.venue_hours_source_url || "").trim() || null,
    verified_at: String(opening.verified_at || schedule.venue_hours_verified_at || "").trim() || null,
  };
}

function consensusExplicitHours(events) {
  const records = events.map(explicitHours).filter(Boolean);
  if (!records.length) return null;
  const byDisplay = new Map();
  for (const record of records) {
    const list = byDisplay.get(record.display) || [];
    list.push(record);
    byDisplay.set(record.display, list);
  }
  if (byDisplay.size !== 1) return null;
  const [display, matches] = [...byDisplay.entries()][0];
  const enriched = matches.find((record) => record.source || record.verified_at) || matches[0];
  return { ...enriched, display };
}

export function venueHoursForEvents(events, cityId) {
  const list = (events || []).filter(Boolean);
  if (!list.length) return null;

  const explicit = consensusExplicitHours(list);
  if (explicit) return explicit;

  if (cityId === "gijon") {
    for (const event of list) {
      const record = gijonVenueHours(event);
      if (record?.display) return { display: record.display, source: record.source || null, verified_at: "2026-08-17" };
    }
    return null;
  }

  if (cityId === "valparaiso") {
    for (const event of list) {
      const name = String(event?.location?.venue || "").trim();
      const record = VALPARAISO_VENUE_HOURS.get(venueKey(name));
      if (record) return record;
    }
  }

  return null;
}

export { VALPARAISO_VENUE_HOURS, venueKey };
