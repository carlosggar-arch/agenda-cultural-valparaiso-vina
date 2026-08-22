import { gijonLocationForEvent, scheduleForGijonEvent } from "./gijon-venue-hours.js?v=20260820-hours1";
import { verifiedGijonEventPage } from "./city-source-evidence-adapter.mjs?v=20260822-source-authority1";

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .trim();
}

function presentationLocationForGijon(event) {
  const location = gijonLocationForEvent(event);
  const venue = fold(location?.venue);
  if (["gijon/xixon", "gijon", "xixon"].includes(venue)) {
    // A city name used as a venue is a source placeholder, not a useful public
    // location. Remove it at the adapter boundary so every common renderer
    // naturally falls back to “Lugar por confirmar”.
    return { ...location, venue: "", city: "" };
  }
  return location;
}

function presentationScheduleForGijon(event) {
  const schedule = scheduleForGijonEvent(event);
  const verified = verifiedGijonEventPage(event);
  if (!verified?.openingTime || !verified?.closingTime) return schedule;
  return {
    ...(schedule || {}),
    opening_time: verified.openingTime,
    closing_time: verified.closingTime,
    hours_confidence: "official_event_page",
  };
}

export function eventForCityPresentation(event, cityId) {
  if (!event || typeof event !== "object") return event;
  if (cityId !== "gijon") return event;
  return {
    ...event,
    location: presentationLocationForGijon(event),
    schedule: presentationScheduleForGijon(event),
  };
}

export function venueHoursForCity(event, cityId) {
  if (!event || typeof event !== "object") return null;
  void cityId;
  // Group headers must not repeat a weekly/seasonal venue schedule because the
  // card represents one concrete viewing date. Date-specific visit hours are
  // rendered later from structured schedule data by the shared presentation
  // layer; when that cannot be determined reliably, showing no hours is safer.
  return null;
}
