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
    write(
        root,
        "fuentes_publicas.json",
        {
            "schema_version": "1.0.0",
            "sources": [
                {
                    "id": "fuente_publica",
                    "name": "Fuente pública",
                    "website_url": "https://example.com",
                    "cities": ["Valparaíso"],
                    "source_type": "Centro cultural",
                    "categories": ["Cultura"],
                    "public_status": "integrada",
                }
            ],
        },
    )
    write(
        root,
        "coverage.json",
        {
            "cities": {
                "valparaiso-vina": {
                    "sources": [{"id": "source_valpo", "name": "Fuente pública"}]
                },
                "gijon": {
                    "sources": [{"id": "gijon_opendata_events", "name": "Open Data Gijón"}]
                },
            }
        },
    )
    write(
        root,
        "valpo.json",
        {"events": [{"id": "v1", "source_id": "source_valpo"}]},
    )
    write(
        root,
        "gijon.json",
        {
            "sources": [{"id": "gijon_opendata_events", "name": "Open Data Gijón"}],
            "events": [
                {
                    "id": "g1",
                    "source_id": "gijon_opendata_events",
                    "links": {
                        "source": "https://opendata.gijon.es/event/1",
                        "official": "https://www.gijon.es/es/evento/1",
                    },
                }
            ],
        },
    )
    return {
        "schema_version": "1.0.0",
        "public_catalog": "fuentes_publicas.json",
        "coverage_catalog": "coverage.json",
        "datasets": [
            {"id": "valparaiso-vina", "path": "valpo.json", "coverage_city_id": "valparaiso-vina"},
            {"id": "gijon", "path": "gijon.json", "coverage_city_id": "gijon"},
        ],
        "name_aliases": {},
        "public_catalog_exceptions": {},
        "verification_policies": {
            "gijon_opendata_events": {
                "policy": "corroboration_required",
                "blocked_public_hosts": ["opendata.gijon.es"],
                "candidate_paths": ["links.official"],
            }
        },
    }


def test_valid_contract_passes() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        report = validate(fixture(root), root)
        assert report["status"] == "ok", report


def test_event_without_source_id_fails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = fixture(root)
        write(root, "valpo.json", {"events": [{"id": "v1"}]})
        report = validate(registry, root)
        assert any("events_without_source_id:1" in error for error in report["errors"])


def test_unknown_source_id_fails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = fixture(root)
        write(root, "valpo.json", {"events": [{"id": "v1", "source_id": "not_registered"}]})
        report = validate(registry, root)
        assert any("events_with_unknown_source_id:1" in error for error in report["errors"])


def test_new_public_source_without_mapping_fails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = fixture(root)
        public = json.loads((root / "fuentes_publicas.json").read_text(encoding="utf-8"))
        public["sources"].append(
            {
                "id": "fuente_nueva",
                "name": "Fuente nueva",
                "website_url": "https://new.example.com",
                "cities": ["Valparaíso"],
                "source_type": "Centro cultural",
                "categories": ["Cultura"],
                "public_status": "integrada",
            }
        )
        write(root, "fuentes_publicas.json", public)
        report = validate(registry, root)
        assert any("public_sources_without_operational_mapping" in error for error in report["errors"])


def test_corroboration_policy_rejects_only_opendata_link() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = fixture(root)
        write(
            root,
            "gijon.json",
            {
                "sources": [{"id": "gijon_opendata_events", "name": "Open Data Gijón"}],
                "events": [
                    {
                        "id": "g1",
                        "source_id": "gijon_opendata_events",
                        "links": {"official": "https://opendata.gijon.es/event/1"},
                    }
                ],
            },
        )
        report = validate(registry, root)
        assert any("verification_policy_failures:1" in error for error in report["errors"])


if __name__ == "__main__":
    test_valid_contract_passes()
    test_event_without_source_id_fails()
    test_unknown_source_id_fails()
    test_new_public_source_without_mapping_fails()
    test_corroboration_policy_rejects_only_opendata_link()
    print("SOURCE_REGISTRY_TESTS_OK")
