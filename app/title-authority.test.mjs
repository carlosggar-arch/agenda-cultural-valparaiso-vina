import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { normalizeAgendaCategories } from "./category-normalizer.js";
import { normalizeAgendaTitles, recoverAgendaTitles } from "./title-normalizer-bootstrap.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const categoryNormalizer = read("./category-normalizer.js");
const categoryRules = read("./public-category-rules.mjs");
const titleNormalizer = read("./title-normalizer-bootstrap.js");
const presentationGuard = read("./public-presentation-guard.js");
const pipeline = read("./data-pipeline.js");

const fixture = {
  events: [{
    id: "venue-title-fixture",
    title: "Museo Palacio Rioja",
    description: "La exposición titulada “Alejandro Sirio. La caligrafía del dibujo” se inaugura esta semana.",
    location: { venue: "Museo Palacio Rioja", city: "Viña del Mar" },
    source_name: "Museo Palacio Rioja",
    primary_category: { id: "otros", label: "Otros" },
    categories: [{ id: "otros", label: "Otros" }],
  }],
};

const recovered = recoverAgendaTitles(fixture);
assert.equal(recovered.events[0].title, "Alejandro Sirio. La caligrafía del dibujo");
assert.equal(recovered.events[0].editorial.title_recovered, true);
assert.equal(recovered.events[0].editorial.category_recovery_hint, "exposiciones");

const categorized = normalizeAgendaCategories(recovered);
assert.equal(categorized.events[0].primary_category.id, "exposiciones");
const normalized = normalizeAgendaTitles(categorized);
assert.equal(normalized.events[0].title, "Alejandro Sirio. La caligrafía del dibujo");
assert.deepEqual(normalizeAgendaTitles(normalized), normalized, "final title normalization must be idempotent");

const categoryPrefixed = normalizeAgendaTitles({
  events: [{
    id: "category-prefix-title-fixture",
    title: "EXPOSICIÓN. La Isla: la pieza que faltaba",
    description: "",
    location: { venue: "Centro cultural", city: "Gijón" },
    primary_category: { id: "exposiciones", label: "Exposiciones" },
    categories: [{ id: "exposiciones", label: "Exposiciones" }],
  }],
});
assert.equal(categoryPrefixed.events[0].title, "La Isla: la pieza que faltaba");
assert.equal(
  categoryPrefixed.events[0].original_title,
  "EXPOSICIÓN. La Isla: la pieza que faltaba",
  "category-label cleanup must preserve source provenance",
);

assert.match(titleNormalizer, /recoverExplicitActivityTitle/);
assert.match(titleNormalizer, /recoverAgendaTitles/);
assert.doesNotMatch(categoryNormalizer, /QUOTED_ACTIVITY|recoverExplicitActivityTitle|repairVenueTitle/, "category normalizer must not recover semantic titles");
assert.doesNotMatch(categoryNormalizer, /category_recovery_hint/, "category normalizer must not bypass the shared semantic classifier");
assert.match(categoryRules, /category_recovery_hint/, "shared category authority may consume a title-owned semantic hint as weighted evidence");
assert.match(categoryRules, /recovery_hint_weight/, "title-owned semantic hints must remain weighted evidence rather than direct authority");

const recoveryIndex = pipeline.indexOf('applyStage("title-recovery"');
const categoryIndex = pipeline.indexOf('applyStage("category-normalizer"');
const normalizationIndex = pipeline.indexOf('applyStage("title-normalizer"');
assert.ok(recoveryIndex >= 0 && recoveryIndex < categoryIndex && categoryIndex < normalizationIndex, "title recovery/category/final normalization order changed");

assert.doesNotMatch(presentationGuard, /normalizePublicTitle|cleanTitleNode|originalPublicTitle/, "public presentation must not normalize titles");
assert.doesNotMatch(presentationGuard, /event-detail-title|grouped-exhibition-copy strong|event-card-body h4|card-body h3/, "public guard must not select title nodes for mutation");

console.log("SINGLE_TITLE_AUTHORITY_OK");
