import { VENUES } from "./venue-registry.generated.mjs?v=20260820-venues1";

function foldVenue(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’‘`]/g, "'")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function venueBase(value) {
  return foldVenue(value).replace(/^(?:museo|museum)\s+/, "").trim();
}

const CULTURAL_COMPLEX_PATTERN = /\b(?:museo|museum|museu|parque cultural|centro cultural|centro de cultura|palacio|galeria|gallery|fundacion)\b/;

const RECORDS = VENUES.map((record) => ({
  ...record,
  _cities: (record.city_names || []).map(foldVenue).filter(Boolean),
  _aliases: [...new Set([record.canonical_name, ...(record.aliases || [])].map(foldVenue).filter(Boolean))]
    .sort((a, b) => b.length - a.length),
  _venueIds: new Set((record.venue_ids || []).map((value) => String(value || "").trim()).filter(Boolean)),
}));

function cityCompatible(record, city) {
  const folded = foldVenue(city);
  if (!folded || !record._cities.length) return true;
  return record._cities.some((candidate) => candidate === folded || candidate.includes(folded) || folded.includes(candidate));
}

function foldedWithoutExactCitySuffix(value, city) {
  const folded = foldVenue(value);
  const cityFolded = foldVenue(city);
  if (!folded || !cityFolded || folded === cityFolded) return folded;
  const suffix = ` ${cityFolded}`;
  return folded.endsWith(suffix) ? folded.slice(0, -suffix.length).trim() : folded;
}

function explicitSubspace(value) {
  return /\b(?:sala|salon|galeria|gallery|hall|auditorio|auditorium|patio|espacio|room|nivel|edificio)\b/.test(foldVenue(value));
}

function parentComplexLabel(value) {
  const raw = String(value || "").replace(/\s+/g, " ").trim();
  if (!raw) return "";
  const parts = raw.split(/\s+[—–-]\s+/u).map((part) => part.trim()).filter(Boolean);
  if (parts.length < 2) return "";
  const tail = parts.at(-1);
  return CULTURAL_COMPLEX_PATTERN.test(foldVenue(tail)) ? tail : "";
}

function directComplexLabel(value) {
  const raw = String(value || "").replace(/\s+/g, " ").trim();
  if (!raw || /\s+[—–-]\s+/u.test(raw)) return "";
  return CULTURAL_COMPLEX_PATTERN.test(foldVenue(raw)) ? raw : "";
}

export function venueRecordForName(value, city = "", venueId = "") {
  const id = String(venueId || "").trim();
  if (id) {
    const byId = RECORDS.find((record) => record._venueIds.has(id) && cityCompatible(record, city));
    if (byId) return byId;
  }

  const folded = foldVenue(value);
  if (!folded) return null;
  const candidates = RECORDS.filter((record) => cityCompatible(record, city));

  for (const record of candidates) {
    if (record._aliases.includes(folded)) return record;
  }

  // Ticketing/aggregator sources frequently append the city after the venue,
  // e.g. “Teatro Mauri SCD, Valparaíso”. Treat that exact city suffix as
  // presentation noise, but never strip arbitrary trailing text.
  const withoutCity = foldedWithoutExactCitySuffix(value, city);
  if (withoutCity && withoutCity !== folded) {
    for (const record of candidates) {
      if (record._aliases.includes(withoutCity)) return record;
    }
  }

  // Containment is intentionally restricted to explicit rooms/subspaces.
  // This groups “Sala Blanca – Museo Baburizza” with its museum without
  // incorrectly collapsing distinct places such as “Jardines Palacio Rioja”.
  if (!explicitSubspace(folded)) return null;
  let best = null;
  let bestLength = 0;
  for (const record of candidates) {
    for (const alias of record._aliases) {
      if (alias.length < 8 || !folded.includes(alias)) continue;
      if (alias.length > bestLength) {
        best = record;
        bestLength = alias.length;
      }
    }
  }
  return best;
}

export function venueRecordForEvent(event) {
  const location = event?.location || {};
  return venueRecordForName(
    location.venue,
    location.city || location.commune,
    location.venue_id,
  );
}

export function canonicalVenueKey(event) {
  const record = venueRecordForEvent(event);
  if (record?.id) return `venue:${record.id}`;
  const venue = venueBase(event?.location?.venue);
  if (!venue) return "";
  const city = foldVenue(event?.location?.city || event?.location?.commune);
  return `${venue}|${city}`;
}

// Exhibition grouping is intentionally broader than physical venue identity.
// A gallery, floor or room keeps its precise location on the event, but an
// explicit "subspace — parent cultural venue" label can share a multi-event
// exhibition card with the parent venue itself.
export function exhibitionGroupingVenueKey(event) {
  const record = venueRecordForEvent(event);
  if (record?.exhibition_group_id) return `exhibition-group:${record.exhibition_group_id}`;
  if (record?.id) return `venue:${record.id}`;
  const venue = event?.location?.venue;
  const complex = parentComplexLabel(venue) || directComplexLabel(venue);
  const city = foldVenue(event?.location?.city || event?.location?.commune);
  if (complex) return `complex:${venueBase(complex)}|${city}`;
  return canonicalVenueKey(event);
}

export function exhibitionGroupingVenueLabel(events) {
  const list = (events || []).filter(Boolean);
  for (const event of list) {
    const record = venueRecordForEvent(event);
    if (record?.exhibition_group_name) return record.exhibition_group_name;
  }
  const parents = list.map((event) => parentComplexLabel(event?.location?.venue)).filter(Boolean);
  if (parents.length) {
    const counts = new Map();
    for (const parent of parents) {
      const key = foldVenue(parent);
      const current = counts.get(key) || { label: parent, count: 0 };
      current.count += 1;
      counts.set(key, current);
    }
    const best = [...counts.values()].sort((a, b) => b.count - a.count || b.label.length - a.label.length)[0];
    if (best?.label) return best.label;
  }
  const canonical = list.map((event) => venueRecordForEvent(event)?.canonical_name).find(Boolean);
  if (canonical) return canonical;
  const direct = list.map((event) => directComplexLabel(event?.location?.venue)).find(Boolean);
  return direct || preferredVenueLabel(list.map((event) => event?.location?.venue));
}

export function canonicalVenueKeyForEvents(events, fallbackLocation = {}) {
  for (const event of events || []) {
    const key = canonicalVenueKey(event);
    if (key) return key;
  }
  const venue = String(fallbackLocation?.venue || "").trim();
  if (!venue) return "";
  return canonicalVenueKey({ location: { ...fallbackLocation, venue } });
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

function finiteCoordinate(value, min, max) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= min && number <= max ? number : null;
}

function canonicalLocationForRecord(record) {
  if (!record) return null;
  const address = String(record.address || "").replace(/\s+/g, " ").trim();
  const coordinates = record.coordinates || {};
  const latitude = finiteCoordinate(coordinates.latitude, -90, 90);
  const longitude = finiteCoordinate(coordinates.longitude, -180, 180);
  const hasCoordinates = latitude !== null && longitude !== null && !(latitude === 0 && longitude === 0);
  if (!address && !hasCoordinates) return null;
  return {
    address: address || null,
    latitude: hasCoordinates ? latitude : null,
    longitude: hasCoordinates ? longitude : null,
  };
}

function structuredVerification(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function enrichCanonicalVenueLocation(event, record) {
  const canonical = canonicalLocationForRecord(record);
  if (!canonical) return event;

  const current = event?.location || {};
  const nextLocation = { ...current };
  const nextEditorial = { ...(event?.editorial || {}) };
  let changed = false;

  const existingAddress = String(current.address || "").replace(/\s+/g, " ").trim();
  if (canonical.address && current.address_verified !== true) {
    if (existingAddress && existingAddress !== canonical.address && !nextEditorial.location_address_original) {
      nextEditorial.location_address_original = existingAddress;
    }
    nextLocation.address = canonical.address;
    nextLocation.address_verified = true;
    changed = true;
  } else if (canonical.address && existingAddress === canonical.address && current.address_verified !== true) {
    nextLocation.address_verified = true;
    changed = true;
  }

  const existingLatitude = finiteCoordinate(current.latitude, -90, 90);
  const existingLongitude = finiteCoordinate(current.longitude, -180, 180);
  const hasVerifiedCoordinates = current.coordinates_verified === true
    && existingLatitude !== null
    && existingLongitude !== null;
  if (canonical.latitude !== null && canonical.longitude !== null && !hasVerifiedCoordinates) {
    if (existingLatitude !== null && existingLongitude !== null && !nextEditorial.location_coordinates_original) {
      nextEditorial.location_coordinates_original = {
        latitude: existingLatitude,
        longitude: existingLongitude,
      };
    }
    nextLocation.latitude = canonical.latitude;
    nextLocation.longitude = canonical.longitude;
    nextLocation.coordinates_verified = true;
    changed = true;
  }

  if (!changed && current.address_verified === true && (canonical.latitude === null || hasVerifiedCoordinates)) return event;

  nextLocation.verification = {
    ...structuredVerification(current.verification),
    status: "verified",
    verified: true,
    method: "canonical_venue_registry",
    source_name: record.location_source_name || null,
    source_url: record.location_source_url || null,
    verified_at: record.location_verified_at || null,
  };
  nextEditorial.canonical_venue_id = record.id || nextEditorial.canonical_venue_id || null;
  nextEditorial.canonical_venue_location = true;

  return {
    ...event,
    location: nextLocation,
    editorial: nextEditorial,
  };
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
    [...labelsByKey.entries()].map(([key, labels]) => {
      const sample = (events || []).find((event) => canonicalVenueKey(event) === key);
      const canonical = venueRecordForEvent(sample)?.canonical_name;
      return [key, canonical || preferredVenueLabel(labels)];
    })
  );

  return (events || []).map((event) => {
    const record = venueRecordForEvent(event);
    const key = canonicalVenueKey(event);
    const preferred = preferredByKey.get(key);
    const current = String(event?.location?.venue || "").trim();
    let normalized = event;

    if (preferred && current && preferred !== current) {
      normalized = {
        ...event,
        location: { ...(event.location || {}), venue: preferred },
        editorial: {
          ...(event.editorial || {}),
          venue_alias_original: event?.editorial?.venue_alias_original || current,
          venue_alias_normalized: true,
          canonical_venue_id: record?.id || event?.editorial?.canonical_venue_id || null,
        },
      };
    }

    // A verified physical location belongs to the venue, not to the source that
    // happened to publish an individual event. Enrich every matched event here
    // so official, ticketing and secondary-source cards share one safe Maps
    // destination without weakening the global no-guess navigation policy.
    return enrichCanonicalVenueLocation(normalized, record || venueRecordForEvent(normalized));
  });
}

export { foldVenue, venueBase, parentComplexLabel, directComplexLabel };
