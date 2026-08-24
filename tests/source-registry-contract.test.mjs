import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const registry = JSON.parse(
  await readFile(new URL("../app/data/source-registry.json", import.meta.url), "utf8"),
);

const VALID_ROLES = new Set([
  "primary",
  "canonical",
  "secondary_channel",
  "discovery_only",
  "enrichment_only",
  "corroborating",
]);

test("source registry exposes one multichannel contract for every city", () => {
  assert.equal(registry.schema_version, "1.0.0");
  assert.equal(registry.contract_version, "1.1.0");
  assert.equal(registry.operational_registry.contract_module, "app/utils/unified_source_registry.py");
  assert.ok(registry.operational_registry.registries.includes("config/sources_gijon.json"));
  assert.ok(registry.operational_registry.registries.includes("data/sources/cultural_sources.json"));
  assert.ok(registry.requirements.all_operational_sources_use_shared_channel_contract);
  assert.ok(registry.requirements.source_migration_must_preserve_event_ids_and_cardinality);
});

test("all declared source roles belong to the canonical role vocabulary", () => {
  assert.deepEqual(new Set(Object.keys(registry.roles)), VALID_ROLES);
});

test("secondary records converge to canonical source identities", () => {
  assert.equal(registry.canonical_source_aliases.artequinvina_instagram, "artequinvina");
  assert.equal(registry.canonical_source_aliases.visita_vina_activities, "culturasvina");
  assert.ok(registry.requirements.secondary_channels_do_not_create_new_canonical_sources);
});

test("new high-value source set is explicitly multi-city", () => {
  const valpo = new Set(registry.new_source_set_2026_08_23.valparaiso_vina);
  const gijon = new Set(registry.new_source_set_2026_08_23.gijon);

  for (const id of [
    "enjoy_vina",
    "culturaviva_vina",
    "duoc_extension_vina",
    "deportes_vina",
    "valpo_deportes",
    "yacht_club_chile",
  ]) {
    assert.ok(valpo.has(id), `missing Valparaíso/Viña source ${id}`);
  }

  for (const id of ["bola8_rock_club", "gijon_life", "planomato_gijon", "pdm_gijon", "surf_asturias"]) {
    assert.ok(gijon.has(id), `missing Gijón source ${id}`);
  }
});

test("pre-publication policies stay in core until a source has public mapping", () => {
  assert.equal(registry.operational_registry.prepublication_policy_owner, "core");
  assert.ok(registry.requirements.discovery_only_cannot_be_final_public_provenance_when_primary_exists);
  assert.ok(registry.requirements.verification_policy_requires_published_source_mapping);

  for (const sourceId of ["planomato_gijon", "corre_valparaiso", "enjoy_vina"]) {
    assert.equal(registry.verification_policies[sourceId], undefined);
  }
});
