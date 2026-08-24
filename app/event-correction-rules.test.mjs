import assert from "node:assert/strict";
import test from "node:test";

import { applyDeclarativeEventCorrectionRules } from "./event-correction-rules.mjs";

const dataset = {
  events: [{ id: "event-1", source_id: "source-a", categories: [{ id: "musica", label: "Música" }] }],
};
const rules = [{
  id: "official-category",
  cityId: "test-city",
  match: { sourceId: "source-a" },
  ensureCategories: [{ id: "teatro", label: "Teatro" }],
  authority: "official_program",
}];

test("applies declared corrections by city and records their authority", () => {
  const corrected = applyDeclarativeEventCorrectionRules(dataset, { cityId: "test-city", rules });
  assert.deepEqual(corrected.events[0].categories.map((category) => category.id), ["musica", "teatro"]);
  assert.deepEqual(corrected.events[0].editorial.applied_correction_rules, ["official-category"]);
  assert.equal(corrected.events[0].editorial.correction_authority, "official_program");
});

test("does not leak a city correction into another city and is idempotent", () => {
  assert.equal(applyDeclarativeEventCorrectionRules(dataset, { cityId: "other-city", rules }), dataset);
  const once = applyDeclarativeEventCorrectionRules(dataset, { cityId: "test-city", rules });
  assert.equal(applyDeclarativeEventCorrectionRules(once, { cityId: "test-city", rules }), once);
});
