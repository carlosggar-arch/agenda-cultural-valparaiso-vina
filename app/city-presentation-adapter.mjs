import { gijonLocationForEvent, scheduleForGijonEvent } from "./gijon-venue-hours.js?v=20260820-hours1";

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
  void cityId;
  // Group headers must not repeat a weekly/seasonal venue schedule because the
  // card represents one concrete viewing date. Date-specific visit hours are
  // rendered later from structured schedule data by the shared presentation
  // layer; when that cannot be determined reliably, showing no hours is safer.
  return null;
}
