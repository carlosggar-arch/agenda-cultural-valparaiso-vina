from __future__ import annotations

from datetime import date

import audit_source_coherence as coherence


def registry() -> dict:
    return {
        "requirements": {
            "event_source_id_required": True,
            "event_source_must_be_registered": True,
            "new_public_source_requires_operational_mapping": True,
        },
        "name_aliases": {
            "Barrio Poniente Viña": "culturasvina",
        },
        "public_catalog_exceptions": {
            "Fuente Pública Legacy": "Pendiente de monitor operativo propio.",
        },
    }


def test_aliases_and_explicit_exceptions_are_not_false_warnings() -> None:
    dataset = {
        "events": [
            {"id": "e1", "source_id": "culturasvina"},
        ]
    }
    coverage = {
        "cities": {
            "valparaiso-vina": {
                "sources": [
                    {"id": "culturasvina", "name": "Culturas Viña"},
                ]
            }
        }
    }
    catalog = {
        "sources": [
            {
                "id": "fuente_barrio",
                "name": "Barrio Poniente Viña",
                "canonical_source_id": "barrio_poniente_vina",
                "last_verified_at": "2099-08-01",
            },
            {
                "id": "fuente_legacy",
                "name": "Fuente Pública Legacy",
                "last_verified_at": "2099-08-01",
            },
        ]
    }

    report = coherence.build(dataset, coverage, catalog, date(2099, 8, 18), registry=registry())
    assert report["status"] == "healthy"
    assert report["public_sources_missing_in_coverage"] == []
    assert report["summary"]["operational_aliases"] == 1
    assert report["summary"]["explicit_catalog_exceptions"] == 1
    assert report["summary"]["registry_state"] == "ok"


def test_source_id_is_required_even_when_source_name_exists() -> None:
    dataset = {"events": [{"id": "e1", "source_name": "Fuente Uno"}]}
    coverage = {"cities": {"valparaiso-vina": {"sources": []}}}
    catalog = {"sources": []}

    report = coherence.build(dataset, coverage, catalog, date(2099, 8, 18), registry=registry())
    assert report["status"] == "critical"
    assert report["unattributed_event_ids"] == ["e1"]
    assert "unattributed_events:1" in report["critical"]


def test_registry_contract_is_enforced() -> None:
    broken = registry()
    broken["requirements"]["event_source_must_be_registered"] = False
    report = coherence.build(
        {"events": []},
        {"cities": {"valparaiso-vina": {"sources": []}}},
        {"sources": []},
        date(2099, 8, 18),
        registry=broken,
    )
    assert report["status"] == "critical"
    assert report["registry_contract_errors"] == ["event_source_must_be_registered"]


def main() -> None:
    test_aliases_and_explicit_exceptions_are_not_false_warnings()
    test_source_id_is_required_even_when_source_name_exists()
    test_registry_contract_is_enforced()
    print("SOURCE_COHERENCE_REGISTRY_TESTS_OK")


if __name__ == "__main__":
    main()
