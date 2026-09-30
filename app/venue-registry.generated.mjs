// Generated runtime bridge for app/data/venue-registry.json.
// Venue facts live only in the JSON registry; do not hardcode them here.
async function loadVenueRegistry() {
  const url = new URL("./data/venue-registry.json", import.meta.url);
  if (url.protocol === "file:") {
    const { readFile } = await import("node:fs/promises");
    return JSON.parse(await readFile(url, "utf8"));
  }
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Venue registry HTTP ${response.status}`);
  return response.json();
}

export const VENUE_REGISTRY = Object.freeze(await loadVenueRegistry());
export const VENUES = Object.freeze(VENUE_REGISTRY.venues || []);
export const EVENT_LOCATION_OVERRIDES = Object.freeze(VENUE_REGISTRY.event_location_overrides || []);
