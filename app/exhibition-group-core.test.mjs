import assert from "node:assert/strict";
import {
  EXHIBITION_GROUP_MIN,
  clusterSimultaneousExhibitions,
  groupStandaloneExhibitions,
  publicExhibitionCategoryId,
} from "./exhibition-group-core.mjs";

const timezone = "Europe/Madrid";
const exhibition = (id, venue, start, end, category = "exposiciones", city = "Gijón") => ({
  id,
  primary_category: { id: category, label: category === "museos" ? "Museos" : "Exposiciones" },
  location: { venue, city },
  schedule: { mode: "multi_day", start, end },
});

assert.equal(EXHIBITION_GROUP_MIN, 2);
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

console.log("Unified exhibition grouping core tests: OK");
