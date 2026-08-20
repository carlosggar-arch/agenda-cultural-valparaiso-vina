import { gijonLocationForEvent, gijonVenueHours, scheduleForGijonEvent } from "./gijon-venue-hours.js?v=20260820-hours1";

export function eventForCityPresentation(event, cityId) {
  if (!event || typeof event !== "object") return event;
  if (cityId !== "gijon") return event;
  return {
    ...event,
    location: gijonLocationForEvent(event),
    schedule: scheduleForGijonEvent(event),
  };
}

export function venueHoursForCity(event, cityId) {
  if (!event || typeof event !== "object") return null;
  if (cityId === "gijon") return gijonVenueHours(event)?.display || null;

  const schedule = event?.schedule || {};
  const opening = schedule?.opening_hours || {};
  const candidates = [
    opening.display_text,
    schedule.venue_opening_hours,
    schedule.visit_hours,
    event?.location?.opening_hours,
  ];
  return candidates.map((value) => String(value || "").replace(/\s+/g, " ").trim()).find(Boolean) || null;
}
