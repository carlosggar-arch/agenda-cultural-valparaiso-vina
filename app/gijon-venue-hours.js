import { EVENT_LOCATION_OVERRIDES } from "./venue-registry.generated.mjs?v=20260820-venues1";
import { venueRecordForEvent } from "./venue-identity.mjs?v=20260820-venues1";

const OVERRIDES = new Map((EVENT_LOCATION_OVERRIDES || []).map((row) => [
  String(row?.official_url || "").replace(/\/$/, ""),
  row,
]).filter(([url]) => url));

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
  const override = OVERRIDES.get(officialEventUrl(event));
  if (!override) return location;
  return {
    ...location,
    venue_id: override.venue_id || location.venue_id,
    venue: override.venue || location.venue,
    address: override.address || location.address,
    verification: override.verification || location.verification,
  };
}

function registryHoursForEvent(event) {
  const location = gijonLocationForEvent(event);
  const record = venueRecordForEvent({ ...event, location });
  return record?.opening_hours || null;
}

export function scheduleForGijonEvent(event) {
  const schedule = event?.schedule;
  if (!schedule || typeof schedule !== "object" || hasExplicitEventTime(schedule)) return schedule;

  const next = { ...schedule, display_text: cleanPlaceholderDisplay(schedule) };
  const venue = registryHoursForEvent(event);
  if (!venue?.display) return next;

  next.opening_hours = {
    mode: "venue",
    display_text: venue.display,
    source_name: venue.source_name || "Horario oficial del recinto",
    source_url: venue.source_url || null,
    verified_at: venue.verified_at || null,
  };
  next.hours_confidence = "official_venue_registry";
  return next;
}

export function gijonVenueHours(event) {
  const venue = registryHoursForEvent(event);
  if (!venue?.display) return null;
  return {
    display: venue.display,
    source: venue.source_url || null,
    source_name: venue.source_name || null,
    verified_at: venue.verified_at || null,
  };
}
