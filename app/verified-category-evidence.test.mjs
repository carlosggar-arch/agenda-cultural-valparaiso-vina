import assert from "node:assert/strict";
import test from "node:test";
import { classifyPublicCategory } from "./public-category-rules.mjs";

const URL = "https://example.org/activities/laboratorio-de-sonidos";
const DATE = "2026-11-07T15:00:00-03:00";
function example() {
  return {
    id: "verified-demo", title: "Laboratorio de sonidos electrónicos",
    source_id: "verified_festival", source_url: URL,
    links: {official: URL + "/"}, schedule: {start: DATE},
    primary_category: {id: "otros", label: "Otros panoramas"},
    categories: [{id: "otros", label: "Otros panoramas"}],
    semantics: {source_category: {id: "musica", label: "Música"}},
    provenance: {verified_category_evidence: {
      contract: "verified-category-evidence/1", authority: "verified_public_events",
      category: {id: "musica", label: "Música"}, source_id: "verified_festival",
      source_url: URL, start: DATE, evidence_url: URL
    }}
  };
}
test("exact-bound category evidence outranks an inferred workshop title", () => {
  const result = classifyPublicCategory(example());
  assert.equal(result.category.id, "musica");
  assert.equal(result.evidence[0].kind, "verified_category_evidence");
});
test("mismatched source, date, URL, or provenance cannot claim priority", () => {
  for (const [field, value] of [
    ["source_id", "other"], ["start", "2026-11-08T15:00:00-03:00"],
    ["source_url", "https://example.org/other"],
    ["authority", "external"], ["contract", "untrusted/1"]
  ]) {
    const item = example();
    item.provenance.verified_category_evidence[field] = value;
    assert.equal(classifyPublicCategory(item).evidence.some(
      r => r.kind === "verified_category_evidence"), false, field);
  }
});
test("reviewed danza maps to canonical Teatro y danza", () => {
  const item = example();
  item.provenance.verified_category_evidence.category = {id: "danza", label: "Danza"};
  item.semantics.source_category = {id: "danza", label: "Danza"};
  assert.equal(classifyPublicCategory(item).category.id, "teatro");
});
