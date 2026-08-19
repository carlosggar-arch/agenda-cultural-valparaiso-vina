function foldVenue(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function venueBase(value) {
  return foldVenue(value).replace(/^(?:museo|museum)\s+/, "").trim();
}

export function canonicalVenueKey(event) {
  const venue = venueBase(event?.location?.venue);
  if (!venue) return "";
  const city = foldVenue(event?.location?.city || event?.location?.commune);
  return `${venue}|${city}`;
}

export function preferredVenueLabel(values) {
  const labels = [...new Set((values || []).map((value) => String(value || "").trim()).filter(Boolean))];
  labels.sort((a, b) => {
    const aMuseum = /^(?:museo|museum)\b/iu.test(a) ? 1 : 0;
    const bMuseum = /^(?:museo|museum)\b/iu.test(b) ? 1 : 0;
    return bMuseum - aMuseum || b.length - a.length || a.localeCompare(b, "es");
  });
  return labels[0] || "";
}

export function normalizeVenueAliases(events) {
  const labelsByKey = new Map();
  for (const event of events || []) {
    const key = canonicalVenueKey(event);
    const venue = String(event?.location?.venue || "").trim();
    if (!key || !venue) continue;
    const labels = labelsByKey.get(key) || [];
    labels.push(venue);
    labelsByKey.set(key, labels);
  }

  const preferredByKey = new Map(
    [...labelsByKey.entries()].map(([key, labels]) => [key, preferredVenueLabel(labels)])
  );

  return (events || []).map((event) => {
    const key = canonicalVenueKey(event);
    const preferred = preferredByKey.get(key);
    const current = String(event?.location?.venue || "").trim();
    if (!preferred || !current || preferred === current) return event;
    return {
      ...event,
      location: { ...(event.location || {}), venue: preferred },
      editorial: {
        ...(event.editorial || {}),
        venue_alias_original: event?.editorial?.venue_alias_original || current,
        venue_alias_normalized: true,
      },
    };
  });
}

export { foldVenue, venueBase };
