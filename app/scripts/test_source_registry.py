from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from validate_source_registry import validate


def write(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def fixture(root: Path) -> dict:
    write(root, "fuentes.json", {"sources": [{"id": "fuente_1", "name": "Fuente pública", "canonical_source_id": "source_valpo"}]})
    write(root, "coverage.json", {"cities": {
        "valparaiso-vina": {"sources": [{"id": "source_valpo", "name": "Fuente operativa"}]},
        "gijon": {"sources": [{"id": "gijon_opendata_events", "name": "Open Data Gijón"}]},
    }})
    write(root, "valpo.json", {"events": [{"id": "v1", "source_id": "source_valpo"}]})
    write(root, "gijon.json", {
        "sources": [{"id": "gijon_opendata_events", "name": "Open Data Gijón"}],
        "events": [{"id": "g1", "source_id": "gijon_opendata_events", "links": {"official": "https://www.gijon.es/evento/1"}}],
    })
    return {
        "schema_version": "1.0.0",
        "public_catalog": "fuentes.json",
        "coverage_catalog": "coverage.json",
        "datasets": [
            {"id": "valparaiso-vina", "path": "valpo.json", "coverage_city_id": "valparaiso-vina"},
            {"id": "gijon", "path": "gijon.json", "coverage_city_id": "gijon"},
        ],
        "name_aliases": {},
        "public_catalog_exceptions": {},
        "verification_policies": {"gijon_opendata_events": {
            "policy": "corroboration_required",
            "blocked_public_hosts": ["opendata.gijon.es"],
            "candidate_paths": ["links.official"],
        }},
    }


def test_valid_contract_passes_with_canonical_source_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = validate(fixture(root), root)
        assert report["status"] == "ok"
        assert report["missing_public_mappings"] == []


def test_event_without_source_id_fails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp); registry = fixture(root)
        write(root, "valpo.json", {"events": [{"id": "v1"}]})
        assert any("events_without_source_id:1" in e for e in validate(registry, root)["errors"])


def test_unknown_source_id_fails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp); registry = fixture(root)
        write(root, "valpo.json", {"events": [{"id": "v1", "source_id": "unknown"}]})
        assert any("events_with_unknown_source_id:1" in e for e in validate(registry, root)["errors"])


def test_new_public_source_without_mapping_fails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp); registry = fixture(root)
        write(root, "fuentes.json", {"sources": [
            {"id": "fuente_1", "name": "Fuente pública", "canonical_source_id": "source_valpo"},
            {"id": "fuente_2", "name": "Fuente nueva", "canonical_source_id": "source_new"},
        ]})
        assert any("public_sources_without_operational_mapping" in e for e in validate(registry, root)["errors"])


def test_explicit_alias_still_supports_different_operational_id() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp); registry = fixture(root)
        write(root, "fuentes.json", {"sources": [{
            "id": "fuente_1", "name": "Fuente pública", "canonical_source_id": "public_identity"
        }]})
        registry["name_aliases"] = {"Fuente pública": "source_valpo"}
        assert validate(registry, root)["status"] == "ok"


def test_redundant_alias_is_reported_for_maintenance() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp); registry = fixture(root)
        registry["name_aliases"] = {"Fuente pública": "source_valpo"}
        report = validate(registry, root)
        assert report["status"] == "ok"
        assert report["maintenance"]["redundant_aliases"] == ["Fuente pública"]


def test_orphan_registry_entries_fail() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp); registry = fixture(root)
        registry["name_aliases"] = {"Fuente inexistente": "source_valpo"}
        registry["public_catalog_exceptions"] = {"Otra inexistente": "legacy"}
        errors = validate(registry, root)["errors"]
        assert any("source_aliases_without_public_source" in error for error in errors)
        assert any("source_exceptions_without_public_source" in error for error in errors)


def test_corroboration_policy_rejects_opendata_only() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp); registry = fixture(root)
        write(root, "gijon.json", {
            "sources": [{"id": "gijon_opendata_events", "name": "Open Data Gijón"}],
            "events": [{"id": "g1", "source_id": "gijon_opendata_events", "links": {"official": "https://opendata.gijon.es/event/1"}}],
        })
        assert any("verification_policy_failures:1" in e for e in validate(registry, root)["errors"])


def test_orphan_verification_policy_fails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp); registry = fixture(root)
        registry["verification_policies"]["ghost_source"] = {"policy": "corroboration_required"}
        assert any(
            "verification_policies_without_registered_source:ghost_source" in error
            for error in validate(registry, root)["errors"]
        )


if __name__ == "__main__":
    test_valid_contract_passes_with_canonical_source_id()
    test_event_without_source_id_fails()
    test_unknown_source_id_fails()
    test_new_public_source_without_mapping_fails()
    test_explicit_alias_still_supports_different_operational_id()
    test_redundant_alias_is_reported_for_maintenance()
    test_orphan_registry_entries_fail()
    test_corroboration_policy_rejects_opendata_only()
    test_orphan_verification_policy_fails()
    print("SOURCE_REGISTRY_TESTS_OK")
