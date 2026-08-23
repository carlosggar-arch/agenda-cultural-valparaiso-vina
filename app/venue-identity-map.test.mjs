import assert from "node:assert/strict";
import { normalizeVenueAliases } from "./venue-identity.mjs";
import { googleMapsDirectionsUrl } from "./public-presentation-rules.mjs";

function normalized(event) {
  return normalizeVenueAliases([event])[0];
}

const laboral = normalized({
  id: "secondary-laboral",
  public_status: { source_official: false },
  location: { venue: "Teatro de la Laboral", city: "Gijón", online: false },
});
assert.equal(laboral.location.address, "Calle Luis Moya Blanco, 261, 33203 Gijón/Xixón, Asturias");
assert.equal(laboral.location.address_verified, true);
assert.equal(laboral.location.verification?.method, "canonical_venue_registry");
assert.match(googleMapsDirectionsUrl(laboral) || "", /^https:\/\/www\.google\.com\/maps\/dir\//);

const mauri = normalized({
  id: "ticket-mauri",
  public_status: { source_official: false },
  location: { venue: "Teatro Mauri SCD, Valparaíso", city: "Valparaíso", online: false },
});
assert.equal(mauri.location.venue, "Teatro Mauri SCD");
assert.equal(mauri.location.address, "Av. Alemania 6985, Cerro Bellavista, Valparaíso");
assert.equal(mauri.location.address_verified, true);
assert.ok(googleMapsDirectionsUrl(mauri));

const rioja = normalized({
  id: "secondary-rioja",
  public_status: { source_official: false },
  location: {
    venue: "Museo Palacio Rioja",
    city: "Viña del Mar",
    address: "Quillota 214, Viña del Mar, Valparaíso",
    online: false,
  },
});
assert.equal(rioja.location.address, "Calle Quillota 214, Viña del Mar");
assert.equal(rioja.location.address_verified, true);
assert.equal(rioja.editorial?.location_address_original, "Quillota 214, Viña del Mar, Valparaíso");
assert.ok(googleMapsDirectionsUrl(rioja));

const acuario = normalized({
  id: "secondary-acuario",
  public_status: { source_official: false },
  location: { venue: "BIOPARC Acuario de Gijón", city: "Gijón", online: false },
});
assert.equal(acuario.location.coordinates_verified, true);
assert.equal(acuario.location.latitude, 43.542138);
assert.equal(acuario.location.longitude, -5.67691);
assert.match(googleMapsDirectionsUrl(acuario) || "", /destination=43\.542138%2C-5\.67691/);

const genericCity = normalized({
  id: "generic-city",
  public_status: { source_official: true },
  location: { venue: "Gijón/Xixón", city: "Gijón", online: false },
});
assert.equal(googleMapsDirectionsUrl(genericCity), null, "a city-wide label must not be turned into a false point destination");

console.log("VENUE_IDENTITY_MAP_ENRICHMENT_OK");
