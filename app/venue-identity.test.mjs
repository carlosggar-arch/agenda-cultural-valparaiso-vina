import assert from "node:assert/strict";
import {
  canonicalVenueKey,
  canonicalVenueKeyForEvents,
  normalizeVenueAliases,
  venueRecordForEvent,
  venueRecordForName,
} from "./venue-identity.mjs";

const event = (venue, city = "Valparaíso", venue_id = null) => ({
  location: { venue, city, venue_id },
});

assert.equal(
  canonicalVenueKey(event("Museo Palacio Rioja", "Viña del Mar")),
  canonicalVenueKey(event("Palacio Rioja", "Viña del Mar")),
);
assert.equal(
  canonicalVenueKey(event("Sala Oriente – Museo Palacio Rioja", "Viña del Mar")),
  canonicalVenueKey(event("Museo Palacio Rioja", "Viña del Mar")),
);
assert.equal(
  canonicalVenueKey(event("Sala Blanca – Museo Baburizza")),
  canonicalVenueKey(event("Museo Baburizza")),
);
assert.notEqual(
  canonicalVenueKey(event("Jardines Palacio Rioja", "Viña del Mar")),
  canonicalVenueKey(event("Museo Palacio Rioja", "Viña del Mar")),
);
assert.equal(
  canonicalVenueKeyForEvents([event("Palacio Rioja", "Viña del Mar")]),
  canonicalVenueKey(event("Museo Palacio Rioja", "Viña del Mar")),
);

const gijon = venueRecordForEvent(event("Nombre secundario", "Gijón", "1118"));
assert.equal(gijon?.id, "museu_pueblu_asturies");
assert.equal(gijon?.canonical_name, "Muséu del Pueblu d'Asturies");

const normalized = normalizeVenueAliases([
  { id: "a", location: { venue: "Museo Baburizza", city: "Valparaíso" }, editorial: {} },
  { id: "b", location: { venue: "Sala Blanca – Museo Baburizza", city: "Valparaíso" }, editorial: {} },
]);
assert.equal(normalized[1].location.venue, "Museo Baburizza");
assert.equal(normalized[1].editorial.venue_alias_original, "Sala Blanca – Museo Baburizza");
assert.equal(normalized[1].editorial.canonical_venue_id, "museo_baburizza");

const mhnv = venueRecordForName("Museo de Historia Natural de Valparaíso", "Valparaíso");
assert.equal(mhnv?.opening_hours?.display, "Mar–vie 10:00–18:00 · sáb 11:00–16:00 · dom/lun/festivos cerrado");
assert.match(mhnv?.opening_hours?.source_url || "", /mhnv\.gob\.cl\/planifica-tu-visita/);
assert.match(mhnv?.opening_hours?.verified_at || "", /^2026-08-20$/);

console.log("VENUE_IDENTITY_CANONICAL_OK");
