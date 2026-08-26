from __future__ import annotations

from datetime import datetime, timezone

from source_health_contract import acquisition_snapshot
from source_pipeline_health import build_city

NOW = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)


def base_dataset(diag: dict) -> dict:
    return {
        "sources": [
            {"id": "cinema", "name": "Cinema", "kind": "instagram", "role": "venue"},
        ],
        "events": [
            {"id": "e1", "source_id": "cinema"},
            {"id": "e2", "source_id": "cinema"},
        ],
        "source_diagnostics": {"cinema": diag},
    }


def test_source_with_events_can_be_stale() -> None:
    dataset = base_dataset({
        "refreshed_at": "2026-08-21T04:00:00-04:00",
        "reviewed_titles": 6,
        "sessions_detected": 8,
        "sessions_published": 8,
    })
    report = build_city("valparaiso-vina", dataset, {}, NOW)
    row = report["sources"][0]
    assert row["published_current_count"] == 2
    assert row["health"] == "stale", row
    assert report["summary"]["stale"] == 1


def test_fresh_source_is_healthy() -> None:
    dataset = base_dataset({
        "last_success_at": "2026-08-26T12:00:00+00:00",
        "raw_items": 4,
        "candidate_events": 2,
        "accepted_events": 2,
        "published_events": 2,
    })
    report = build_city("valparaiso-vina", dataset, {}, NOW)
    assert report["sources"][0]["health"] == "healthy"


def test_fetch_failure_is_warning_not_critical() -> None:
    snap = acquisition_snapshot({
        "last_success_at": "2026-08-26T12:00:00+00:00",
        "fetch_ok": False,
    }, NOW, source_type="instagram", role="venue")
    assert snap["health"] == "fetch_failed"
    assert snap["severity"] == "warning"


def test_changed_content_without_candidates_is_warning() -> None:
    snap = acquisition_snapshot({
        "last_success_at": "2026-08-26T12:00:00+00:00",
        "content_changed": True,
        "raw_items": 3,
        "candidate_events": 0,
    }, NOW, source_type="instagram")
    assert snap["health"] == "content_changed_not_processed"
    assert snap["severity"] == "warning"


def test_candidates_rejected_is_visible() -> None:
    snap = acquisition_snapshot({
        "last_success_at": "2026-08-26T12:00:00+00:00",
        "candidate_events": 3,
        "accepted_events": 0,
    }, NOW, source_type="instagram")
    assert snap["health"] == "candidates_rejected"
    assert snap["severity"] == "warning"


def test_accepted_not_published_is_critical() -> None:
    snap = acquisition_snapshot({
        "last_success_at": "2026-08-26T12:00:00+00:00",
        "candidate_events": 4,
        "accepted_events": 3,
        "published_events": 2,
    }, NOW, source_type="instagram")
    assert snap["health"] == "accepted_not_published"
    assert snap["severity"] == "critical"


def test_covered_elsewhere_does_not_raise_stale_warning() -> None:
    dataset = {
        "sources": [{"id": "source_a", "name": "A", "kind": "instagram"}],
        "events": [],
        "source_diagnostics": {"source_a": {"refreshed_at": "2026-08-20T00:00:00+00:00"}},
    }
    coverage = {"sources": [{"id": "source_a", "covered_by_other_sources": ["source_b"]}]}
    report = build_city("valparaiso-vina", dataset, coverage, NOW)
    assert report["sources"][0]["health"] == "covered_elsewhere"
    assert report["summary"]["warning_sources"] == 0


def main() -> None:
    test_source_with_events_can_be_stale()
    test_fresh_source_is_healthy()
    test_fetch_failure_is_warning_not_critical()
    test_changed_content_without_candidates_is_warning()
    test_candidates_rejected_is_visible()
    test_accepted_not_published_is_critical()
    test_covered_elsewhere_does_not_raise_stale_warning()
    print("SOURCE_PIPELINE_HEALTH_TESTS_OK")


if __name__ == "__main__":
    main()
