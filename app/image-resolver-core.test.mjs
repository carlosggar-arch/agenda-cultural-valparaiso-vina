import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  buildVenueImagePools,
  categoryFallbackImage,
  generatedEventFallbackImage,
  isGenericProviderImage,
  looksLikeGenericSchedule,
  relevantEventImageUrl,
  resolveCardImageAfterFailure,
  resolveEventImage,
  shouldInstallCategoryFallback,
  venueImageKey,
} from "./image-resolver-core.mjs";

const BASE = "https://vivamos.pages.dev/app/";
const ROOT_BASE = "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina/";

function legacyFoldWords(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function legacyGenericSchedule(event) {
  if (event?.image?.relevance === "generic_schedule") return true;
  const title = legacyFoldWords(event?.title);
  const description = legacyFoldWords(event?.description);
  if (/\b(agenda|cartelera|programacion|calendario|panoramas?)\b/.test(title)) return true;
  if (/^(?:destino|panoramas?) .+ (?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre) 20\d{2}$/.test(title)) return true;
  const mentions = (String(event?.description || "").match(/@[a-z0-9_.]+/gi) || []).length;
  return /\beste mes (?:tenemos|incluye|trae|hay)\b/.test(description) && mentions >= 2;
}

function legacySafe(value) {
  if (!value) return null;
  try {
    const url = new URL(String(value), BASE);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function legacyRelevant(event) {
  return legacyGenericSchedule(event) ? null : legacySafe(event?.image?.url);
}

function legacyVenueKey(event) {
  const city = legacyFoldWords(event?.location?.city);
  let venue = legacyFoldWords(event?.location?.venue);
  if (!city || !venue || venue === city || /^(?:online|sitio web)\b/.test(venue)) return null;
  if (venue.endsWith(` ${city}`)) venue = venue.slice(0, -(city.length + 1)).trim();
  return venue ? `${city}|${venue}` : null;
}

function legacyPools(events) {
  const pools = new Map();
  for (const event of events) {
    const key = legacyVenueKey(event);
    const url = legacyRelevant(event);
    if (!key || !url) continue;
    const pool = pools.get(key) || [];
    if (!pool.includes(url)) pool.push(url);
    pools.set(key, pool);
  }
  return pools;
}

function legacyRepresentative(event, pools) {
  if (legacyGenericSchedule(event)) return null;
  const key = legacyVenueKey(event);
  return key ? pools.get(key)?.[0] || null : null;
}

const own = {
  id: "own",
  title: "Concierto de cámara",
  location: { city: "Gijón", venue: "Teatro Jovellanos" },
  image: { url: "https://img.example/own.jpg" },
  primary_category: { id: "musica", label: "Música" },
};
const sibling = {
  id: "sibling",
  title: "Otra función",
  location: { city: "Gijón", venue: "Teatro Jovellanos" },
  image: { url: "https://img.example/venue.jpg" },
  primary_category: { id: "teatro", label: "Teatro" },
};
const noImage = {
  id: "missing",
  title: "Actividad sin foto",
  location: { city: "Gijón", venue: "Teatro Jovellanos" },
  primary_category: { id: "teatro", label: "Teatro" },
};
const noImageNoVenuePool = {
  id: "missing-unique",
  title: "Club de lectura infantil",
  location: { city: "Valparaíso", venue: "Biblioteca de Playa Ancha" },
  primary_category: { id: "cursos-talleres-campus", label: "Cursos, talleres y experiencias" },
};
const genericSchedule = {
  id: "agenda",
  title: "Agenda cultural agosto 2026",
  description: "Este mes tenemos @uno y @dos",
  location: { city: "Gijón", venue: "Teatro Jovellanos" },
  image: { url: "https://img.example/agenda.jpg" },
  primary_category: { id: "cultura", label: "Cultura" },
};

const events = [own, sibling, noImage, genericSchedule];
const pools = buildVenueImagePools(events, { baseUrl: BASE });
const oldPools = legacyPools(events);

test("card direct and same-venue representative resolution remains stable where a real image exists", () => {
  for (const event of [own, sibling, noImage]) {
    assert.equal(looksLikeGenericSchedule(event), legacyGenericSchedule(event));
    assert.equal(relevantEventImageUrl(event, { baseUrl: BASE }), legacyRelevant(event));
    assert.equal(venueImageKey(event), legacyVenueKey(event));
    const expected = legacyRelevant(event) || legacyRepresentative(event, oldPools);
    assert.equal(resolveEventImage(event, { surface: "card", venueImagePools: pools, baseUrl: BASE }).url, expected);
  }
});

test("failed direct card image still prefers the exact legacy same-venue URL", () => {
  const expected = legacyRepresentative(own, oldPools);
  const ownFallback = resolveCardImageAfterFailure(own, legacyRelevant(own), { venueImagePools: pools, baseUrl: BASE });
  assert.equal(ownFallback.url,
    expected === legacyRelevant(own) ? categoryFallbackImage(own).url : expected);
  const failing = { ...own, id: "failing", image: { url: "https://img.example/failing.jpg" } };
  const expectedFallback = legacyRepresentative(failing, oldPools);
  const resolvedFallback = resolveCardImageAfterFailure(failing, legacyRelevant(failing), { venueImagePools: oldPools, baseUrl: BASE });
  assert.equal(resolvedFallback.url,
    expectedFallback === legacyRelevant(failing) ? categoryFallbackImage(failing).url : expectedFallback);
});

test("every ordinary card gets a graphical category image when no source or venue image exists", () => {
  const resolved = resolveEventImage(noImageNoVenuePool, { surface: "card", venueImagePools: pools, baseUrl: BASE });
  assert.deepEqual(resolved, { ...categoryFallbackImage(noImageNoVenuePool), genericSchedule: false });
});

test("generic schedule suppresses unrelated source art and gets a graphical category image", () => {
  assert.equal(relevantEventImageUrl(genericSchedule, { baseUrl: BASE }), null);
  const resolved = resolveEventImage(genericSchedule, { surface: "card", venueImagePools: pools, baseUrl: BASE });
  assert.equal(resolved.kind, "category-fallback");
  assert.equal(resolved.genericSchedule, true);
});

test("descriptive filenames never override verified event-image quality", () => {
  const event = {
    title: "Nebulosa Carina",
    primary_category: { id: "exposiciones", label: "Exposiciones" },
    location: { city: "Valparaíso", venue: "Museo Baburizza" },
    image: { url: "https://www.museobaburizza.cl/wp-content/uploads/2026/07/evento-nebulosacarina-portada-1.jpg" },
  };
  assert.equal(relevantEventImageUrl(event, { baseUrl: BASE }), event.image.url);
  assert.equal(resolveEventImage(event, { baseUrl: BASE }).url, event.image.url);
});

test("official photographic covers remain eligible when filename contains portada", () => {
  const event = {
    title: "Las cumbias que escuchamos allá arriba",
    primary_category: { id: "exposiciones", label: "Exposiciones" },
    location: { city: "Valparaíso", venue: "Museo Baburizza" },
    image: { url: "https://www.museobaburizza.cl/wp-content/uploads/2026/07/evento-lascumbias-portada-1.jpg" },
  };
  assert.equal(relevantEventImageUrl(event, { baseUrl: BASE }), event.image.url);
  assert.equal(resolveEventImage(event, { baseUrl: BASE }).kind, "relevant");
});

test("explicit quality metadata rejects typographic art from every source", () => {
  const event = {
    title: "Actividad",
    primary_category: { id: "teatro", label: "Teatro y danza" },
    image: { url: "https://images.example/poster.jpg", visual_quality: "text_heavy" },
  };
  assert.equal(relevantEventImageUrl(event, { baseUrl: BASE }), null);
});

test("group surface preserves raw event image policy and exact URL string", () => {
  const raw = { ...own, image: { url: "https://img.example/a%20b.jpg" } };
  assert.equal(resolveEventImage(raw, { surface: "group" }).url, "https://img.example/a%20b.jpg");
  assert.equal(resolveEventImage(noImage, { surface: "group" }).url, null);
  assert.equal(resolveEventImage(genericSchedule, { surface: "group" }).url, genericSchedule.image.url);
  const cached = { ...own, image: { url: "./assets/event-images/gijon/event.webp" } };
  assert.equal(
    resolveEventImage(cached, { surface: "group", baseUrl: BASE }).url,
    new URL("./assets/event-images/gijon/event.webp", BASE).href,
  );
  assert.equal(
    resolveEventImage(cached, { surface: "card", baseUrl: ROOT_BASE }).url,
    new URL("./app/assets/event-images/gijon/event.webp", ROOT_BASE).href,
  );
});

test("root WEB consumes the shared multicity image URL resolver", () => {
  const webSource = readFileSync(new URL("../assets/agenda.js", import.meta.url), "utf8");
  assert.match(webSource, /import \{ safeHttpImageUrl \} from "\.\.\/app\/image-resolver-core\.mjs/);
  assert.match(webSource, /safeHttpImageUrl\(event\.image\?\.url, \{ baseUrl: location\.href \}\)/);
  assert.doesNotMatch(webSource, /safeHttpUrl\(event\.image\?\.url\)/);
});

test("detail surface preserves safe direct-image policy and explicit suppression", () => {
  assert.equal(resolveEventImage(own, { surface: "detail", baseUrl: BASE }).url, legacySafe(own.image.url));
  const generatedDetail = resolveEventImage(noImageNoVenuePool, { surface: "detail", baseUrl: BASE });
  assert.equal(generatedDetail.kind, "category-fallback");
  assert.equal(resolveEventImage(own, { surface: "detail", baseUrl: BASE, allowDirect: false }).url, null);
});

test("category fallback preserves current category and label mapping", () => {
  assert.equal(categoryFallbackImage(own).url, "../assets/categoria-musica.jpg");
  assert.equal(categoryFallbackImage(noImage).url, "../assets/categoria-teatro.jpg");
  assert.equal(categoryFallbackImage(null, { categoryHint: "museos" }).url, "../assets/categoria-exposiciones.jpg");
  assert.equal(categoryFallbackImage(null, { labelHint: "Naturaleza y caminatas" }).url, "../assets/categoria-naturaleza.jpg");
  assert.equal(categoryFallbackImage(null, { labelHint: "Sin clasificar" }).url, "../assets/categoria-cultura.jpg");
});

test("quality guard generic-provider replacement remains explicit", () => {
  const generic = "https://passline.com/assets/img/placeholder.png";
  const specific = "https://passline.com/uploads/evento-real.jpg";
  assert.equal(isGenericProviderImage(generic, { baseUrl: BASE }), true);
  assert.equal(isGenericProviderImage(specific, { baseUrl: BASE }), false);
  assert.equal(shouldInstallCategoryFallback({ placeholder: true, hasImage: false }, { baseUrl: BASE }), true);
  assert.equal(shouldInstallCategoryFallback({ placeholder: false, hasImage: true, currentUrl: generic }, { baseUrl: BASE }), true);
  assert.equal(shouldInstallCategoryFallback({ placeholder: false, hasImage: true, currentUrl: specific }, { baseUrl: BASE }), false);
});
