import assert from "node:assert/strict";
import {
  EXHIBITION_GROUP_MIN,
  LONG_EXHIBITION_DAYS,
  clusterSimultaneousExhibitions,
  exhibitionDurationDays,
  exhibitionVenueKey,
  groupStandaloneExhibitions,
  isLongExhibitionDuration,
  partitionExhibitionsByDuration,
  publicExhibitionCategoryId,
} from "./exhibition-group-core.mjs";

const timezone = "Europe/Madrid";
const durationOptions = { timezone };
const exhibition = (id, venue, start, end, category = "exposiciones", city = "Gijón") => ({
  id,
  primary_category: { id: category, label: category === "museos" ? "Museos" : "Exposiciones" },
  location: { venue, city },
  schedule: { mode: "multi_day", start, end },
});

assert.equal(EXHIBITION_GROUP_MIN, 2);
assert.equal(LONG_EXHIBITION_DAYS, 7);
assert.equal(publicExhibitionCategoryId(exhibition("m1", "Museo", "2026-08-01", "2026-08-31", "museos")), "exposiciones");

const simultaneous = [
  exhibition("a", "Muséu del Pueblu d'Asturies", "2026-08-01", "2026-09-01"),
  exhibition("b", "Muséu del Pueblu d'Asturies", "2026-08-10", "2026-08-25"),
  exhibition("c", "Muséu del Pueblu d'Asturies", "2026-08-15", "2026-08-30"),
];
const clusters = clusterSimultaneousExhibitions(simultaneous, { timezone });
assert.equal(clusters.length, 1);
assert.equal(clusters[0].events.length, 3);

const grouped = groupStandaloneExhibitions(simultaneous, { timezone });
assert.equal(grouped.length, 1);
assert.equal(grouped[0].events.length, 3);

const riojaAliases = [
  exhibition("rioja-canonical", "Museo Palacio Rioja", "2026-08-01", "2026-08-31", "exposiciones", "Viña del Mar"),
  exhibition("rioja-alias", "Palacio Rioja", "2026-08-03", "2026-08-28", "exposiciones", "Viña del Mar"),
  exhibition("rioja-gardens", "Jardines Palacio Rioja", "2026-08-03", "2026-08-28", "exposiciones", "Viña del Mar"),
];
assert.equal(exhibitionVenueKey(riojaAliases[0]), exhibitionVenueKey(riojaAliases[1]));
assert.notEqual(exhibitionVenueKey(riojaAliases[0]), exhibitionVenueKey(riojaAliases[2]));
const riojaGroups = groupStandaloneExhibitions(riojaAliases, { timezone: "America/Santiago" });
assert.equal(riojaGroups.length, 1, "registered aliases must converge before exhibition grouping");
assert.deepEqual(riojaGroups[0].events.map((item) => item.id), ["rioja-canonical", "rioja-alias"]);

const pcvSubspaces = [
  exhibition("pcv-gallery", "Galería de Artes Visuales — Parque Cultural de Valparaíso", "2026-08-06", "2026-09-24", "exposiciones", "Valparaíso"),
  exhibition("pcv-reos", "1º nivel del Edificio de la Ex Galería de Reos — Parque Cultural de Valparaíso", "2026-07-10", "2026-08-30", "exposiciones", "Valparaíso"),
  exhibition("pcv-direct", "Parque Cultural de Valparaíso", "2026-08-01", "2026-08-31", "exposiciones", "Valparaíso"),
];
const pcvGroups = groupStandaloneExhibitions(pcvSubspaces, { timezone: "America/Santiago" });
assert.equal(pcvGroups.length, 1, "explicit PCV subspaces must share the parent exhibition complex");
assert.deepEqual(new Set(pcvGroups[0].events.map((item) => item.id)), new Set(["pcv-gallery", "pcv-reos", "pcv-direct"]));

const naturalHistory = [
  exhibition("mhnv-biodiversity", "Museo de Historia Natural de Valparaíso", "2026-08-01", "2026-12-31", "museos", "Valparaíso"),
  exhibition("mhnv-temporary", "Museo de Historia Natural de Valparaíso", "2026-08-13", "2026-09-20", "exposiciones", "Valparaíso"),
];
const mhnvGroups = groupStandaloneExhibitions(naturalHistory, { timezone: "America/Santiago" });
assert.equal(mhnvGroups.length, 1, "museum and exhibition labels at MHNV must converge into one multi-event card");
assert.deepEqual(mhnvGroups[0].events.map((item) => item.id), ["mhnv-biodiversity", "mhnv-temporary"]);

const nonOverlapping = [
  exhibition("early", "Museo común", "2026-01-01", "2026-01-31"),
  exhibition("late", "Museo común", "2026-03-01", "2026-03-31"),
];
assert.equal(groupStandaloneExhibitions(nonOverlapping, { timezone }).length, 0);

const differentVenues = [
  exhibition("x", "Museo A", "2026-08-01", "2026-08-31"),
  exhibition("y", "Museo B", "2026-08-01", "2026-08-31"),
];
assert.equal(groupStandaloneExhibitions(differentVenues, { timezone }).length, 0);

const exactlySevenDays = exhibition("seven", "Museo mixto", "2026-08-01", "2026-08-08");
const moreThanSevenDays = exhibition("eight", "Museo mixto", "2026-08-01", "2026-08-09");
assert.equal(exhibitionDurationDays(exactlySevenDays, durationOptions), 7);
assert.equal(isLongExhibitionDuration(exactlySevenDays, durationOptions), false, "exactly seven days must remain in chronological flow");
assert.equal(exhibitionDurationDays(moreThanSevenDays, durationOptions), 8);
assert.equal(isLongExhibitionDuration(moreThanSevenDays, durationOptions), true, "more than seven days must be deferred when no category is active");

const mixedDurationSameVenue = [
  exhibition("short-1", "Museo mixto", "2026-08-01", "2026-08-08"),
  exhibition("short-2", "Museo mixto", "2026-08-02", "2026-08-08"),
  exhibition("long-1", "Museo mixto", "2026-08-01", "2026-08-15"),
  exhibition("long-2", "Museo mixto", "2026-08-02", "2026-08-20"),
];
const partitions = partitionExhibitionsByDuration(mixedDurationSameVenue, durationOptions);
assert.deepEqual(partitions.regular.map((event) => event.id), ["short-1", "short-2"]);
assert.deepEqual(partitions.long.map((event) => event.id), ["long-1", "long-2"]);

const crossDurationGroups = groupStandaloneExhibitions(mixedDurationSameVenue, {
  timezone,
  minSize: EXHIBITION_GROUP_MIN,
});
assert.equal(crossDurationGroups.length, 1, "still-standalone exhibitions may group across duration classes");
assert.deepEqual(crossDurationGroups[0].events.map((event) => event.id), ["short-1", "long-1", "short-2", "long-2"]);

const pinoleMixedCategories = [
  exhibition("pinole-itinerary", "Museo Nicanor Piñole", "2026-08-22", "2026-08-22", "museos"),
  exhibition("pinole-sirio", "Museo Nicanor Piñole", "2026-03-12", "2026-08-23", "exposiciones"),
];
const pinoleGroups = groupStandaloneExhibitions(pinoleMixedCategories, { timezone, minSize: EXHIBITION_GROUP_MIN });
assert.equal(pinoleGroups.length, 1, "museum/exhibition labels must not prevent same-venue grouping");
assert.deepEqual(pinoleGroups[0].events.map((event) => event.id), ["pinole-sirio", "pinole-itinerary"]);

console.log("Unified exhibition grouping core tests: OK");
