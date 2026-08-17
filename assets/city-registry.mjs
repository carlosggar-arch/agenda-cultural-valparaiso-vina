export const CITY_STORAGE_KEY = "agenda-cultural-city";
export const CITY_REGISTRY_URL = new URL("../app/cities.json", import.meta.url);

let registryPromise = null;

export function normalizeCityId(value) {
  return String(value ?? "").trim().toLocaleLowerCase("en-US");
}

export function isSafeCityId(value) {
  return /^[a-z0-9][a-z0-9-]{0,63}$/.test(normalizeCityId(value));
}

function freezeCity(raw) {
  const city = {
    ...raw,
    id: normalizeCityId(raw?.id),
    areas: Array.isArray(raw?.areas) ? raw.areas.map((area) => Object.freeze({
      ...area,
      id: normalizeCityId(area?.id),
      match: Array.isArray(area?.match) ? Object.freeze([...area.match]) : Object.freeze([]),
    })) : [],
    center: Object.freeze({ ...(raw?.center || {}) }),
    visual: Object.freeze({ ...(raw?.visual || {}) }),
  };
  city.areas = Object.freeze(city.areas);
  return Object.freeze(city);
}

function validateRegistry(payload) {
  if (!payload || typeof payload !== "object" || !Array.isArray(payload.cities)) {
    throw new Error("Invalid city registry payload");
  }
  const cities = payload.cities.map(freezeCity);
  if (!cities.length) throw new Error("City registry is empty");
  const byId = {};
  for (const city of cities) {
    if (!isSafeCityId(city.id)) throw new Error(`Invalid city id: ${city.id}`);
    for (const field of ["label", "timezone", "locale", "dataset"]) {
      if (!String(city[field] || "").trim()) throw new Error(`City ${city.id} missing ${field}`);
    }
    if (byId[city.id]) throw new Error(`Duplicate city id: ${city.id}`);
    byId[city.id] = city;
  }
  const defaultCityId = normalizeCityId(payload.default_city);
  if (!byId[defaultCityId]) throw new Error(`Unknown default city: ${defaultCityId}`);
  return Object.freeze({
    schemaVersion: String(payload.schema_version || ""),
    defaultCityId,
    cities: Object.freeze(cities),
    byId: Object.freeze(byId),
  });
}

export function loadCityRegistry({ refresh = false } = {}) {
  if (!registryPromise || refresh) {
    registryPromise = fetch(CITY_REGISTRY_URL, { headers: { Accept: "application/json" }, cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`City registry HTTP ${response.status}`);
        return response.json();
      })
      .then(validateRegistry)
      .catch((error) => {
        registryPromise = null;
        throw error;
      });
  }
  return registryPromise;
}

export function cityFromRegistry(registry, value) {
  const id = normalizeCityId(value);
  return registry?.byId?.[id] || null;
}
