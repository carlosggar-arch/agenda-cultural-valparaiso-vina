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

const pucvCasaCentral = normalized({
  id: "pucv-leadership-workshop",
  public_status: { source_official: true },
  source_url: "https://www.pucv.cl/",
  location: { venue: "Casa Central", city: "Valparaíso", online: false },
});
assert.equal(pucvCasaCentral.location.venue, "Casa Central PUCV");
assert.equal(pucvCasaCentral.location.address, "Av. Brasil 2950, Valparaíso");
assert.equal(pucvCasaCentral.location.address_verified, true);
assert.ok(googleMapsDirectionsUrl(pucvCasaCentral));

const genericCity = normalized({
  id: "generic-city",
  public_status: { source_official: true },
  location: { venue: "Gijón/Xixón", city: "Gijón", online: false },
});
assert.equal(googleMapsDirectionsUrl(genericCity), null, "a city-wide label must not be turned into a false point destination");

console.log("VENUE_IDENTITY_MAP_ENRICHMENT_OK");

for (const [title, venue, address, city] of [
  ["Escuelita Exploradores", "Museo Artequin", "Alcalde Prieto Nieto Parque, Potrerillos 500", "Viña del Mar"],
  ["Qi Gong", "Palacio Rioja, Jardines", "Quillota 214", "Viña del Mar"],
  ["Teatro para adultos", "Duoc UC Sede Viña del Mar", "Álvarez 2366", "Viña del Mar"],
  ["Actividad", "Recinto acreditado", "Calle del ejemplo 10", "Gijón"],
]) {
  const source = "https://example.org/agenda/actividad/";
  const event = {
    title,
    source_url: source,
    public_status: { source_official: false },
    location: { venue, address, city, online: false, venue_id: null, latitude: null, longitude: null },
    provenance: { official_metadata: [{
      url: source,
      method: "official_page_structured_or_event_local_evidence",
      fields: ["address"],
    }] },
  };
  const original = structuredClone(event);
  const url = new URL(googleMapsDirectionsUrl(event));
  assert.equal(url.searchParams.get("destination"), `${venue}, ${address}, ${city}`);
  assert.equal(new URL(googleMapsDirectionsUrl({ ...event,
    location: { ...event.location, latitude: 1, longitude: 2 },
  })).searchParams.get("destination"), `${venue}, ${address}, ${city}`, "address provenance does not verify unrelated coordinates");
  assert.deepEqual(event, original, "maps must not mutate source evidence");
  assert.equal(googleMapsDirectionsUrl({ ...event, location: { ...event.location, online: true } }), null);
  assert.equal(googleMapsDirectionsUrl({ ...event, location: { ...event.location, address: null } }), null);
  assert.equal(googleMapsDirectionsUrl({ ...event, source_url: "https://example.org/unrelated/" }), null);
  assert.equal(googleMapsDirectionsUrl({ ...event, provenance: { official_metadata: [{
    ...event.provenance.official_metadata[0], fields: ["image", "price"],
  }] } }), null);
  assert.equal(googleMapsDirectionsUrl({ ...event, provenance: null,
    location: { ...event.location, venue_id: "unverified-id" } }), null);
}
console.log("EVENT_LOCAL_ADDRESS_EVIDENCE_MAP_OK");

const catalogAddress = {
  title: "Actividad en recinto acreditado",
  location: { venue: "Museo Artequin", address: "Alcalde Prieto Nieto 500", city: "Viña del Mar", online: false },
  public_status: { source_official: false },
  provenance: { verified_venue: {
    method: "canonical_venue_registry", venue_id: "artequin-vina",
    address: "Alcalde Prieto Nieto 500", city: "Viña del Mar",
    source_url: "https://www.artequinvina.cl/", verified_at: "2026-09-21",
  } },
};
const catalogUrl = new URL(googleMapsDirectionsUrl(catalogAddress));
assert.equal(catalogUrl.searchParams.get("destination"), "Museo Artequin, Alcalde Prieto Nieto 500, Viña del Mar");
assert.equal(new URL(googleMapsDirectionsUrl({ ...catalogAddress,
  location: { ...catalogAddress.location, latitude: 1, longitude: 2 },
})).searchParams.get("destination"), catalogUrl.searchParams.get("destination"));
for (const changes of [
  { address: "Otra calle 500" }, { city: "Valparaíso" }, { venue_id: "other-venue" }, { online: true },
]) assert.equal(googleMapsDirectionsUrl({ ...catalogAddress, location: { ...catalogAddress.location, ...changes } }), null);
for (const changes of [
  { method: "unverified" }, { venue_id: "" }, { source_url: "http://example.org/" },
  { source_url: "https://user:secret@example.org/" }, { verified_at: "" },
]) assert.equal(googleMapsDirectionsUrl({ ...catalogAddress, provenance: { verified_venue: {
  ...catalogAddress.provenance.verified_venue, ...changes,
} } }), null);
console.log("CANONICAL_ADDRESS_PROVENANCE_MAP_OK");
