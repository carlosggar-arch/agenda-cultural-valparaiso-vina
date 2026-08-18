from __future__ import annotations

from refresh_quality_diagnostics import coverage_report


def _event(source_id: str, source_name: str) -> dict:
    return {
        "id": f"event-{source_id}",
        "source_id": source_id,
        "source_name": source_name,
        "schedule": {"start": "2099-08-20T19:00:00"},
        "location": {"city": "Test", "venue": "Test venue"},
        "links": {"official": "https://example.com/event"},
        "public_status": {"source_official": True},
        "price": {"is_free": True},
        "image": {"url": "https://example.com/image.jpg"},
    }


def _dataset(prefix: str) -> dict:
    return {
        "sources": [
            {
                "id": f"{prefix}_active",
                "name": f"{prefix} active",
                "kind": "web_calendar",
                "source_role": "venue",
            },
            {
                "id": f"{prefix}_zero",
                "name": f"{prefix} zero",
                "kind": "instagram",
                "source_role": "organizer",
            },
        ],
        "events": [_event(f"{prefix}_active", f"{prefix} active")],
    }


def test_catalogued_zero_sources_are_kept_for_both_city_scopes() -> None:
    datasets = {
        "valparaiso-vina": _dataset("valpo"),
        "gijon": _dataset("gijon"),
    }
    report = coverage_report({}, datasets, "2099-08-18T12:00:00+00:00")

    for city_id, prefix in (("valparaiso-vina", "valpo"), ("gijon", "gijon")):
        city = report["cities"][city_id]
        rows = {row["id"]: row for row in city["sources"]}
        assert city["summary"]["sources_total"] == 2
        assert city["summary"]["producing_now"] == 1
        assert city["summary"]["zero_now"] == 1
        assert rows[f"{prefix}_active"]["current_count"] == 1
        assert rows[f"{prefix}_zero"]["current_count"] == 0
        assert rows[f"{prefix}_zero"]["source_type"] == "instagram"
        assert rows[f"{prefix}_zero"]["role"] == "organizer"


if __name__ == "__main__":
    test_catalogued_zero_sources_are_kept_for_both_city_scopes()
    print("MULTICITY_SOURCE_REGISTRY_COVERAGE_OK")
