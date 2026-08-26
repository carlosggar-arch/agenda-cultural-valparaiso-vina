from __future__ import annotations

from datetime import datetime, timezone

from source_health_contract import acquisition_snapshot, canonical_acquisition_receipt
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


def test_source_with_events_can_be_stale_without_blocking_publication() -> None:
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
    assert row["publication_blocking"] is False
    assert report["summary"]["stale"] == 1
    assert report["summary"]["critical_sources"] == 0


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
    assert snap["publication_blocking"] is False


def test_changed_content_without_candidates_is_warning() -> None:
    snap = acquisition_snapshot({
        "last_success_at": "2026-08-26T12:00:00+00:00",
        "content_changed": True,
        "raw_items": 3,
        "candidate_events": 0,
    }, NOW, source_type="instagram")
    assert snap["health"] == "content_changed_not_processed"
    assert snap["severity"] == "warning"
    assert snap["publication_blocking"] is False


def test_candidates_rejected_is_visible_but_local() -> None:
    snap = acquisition_snapshot({
        "last_success_at": "2026-08-26T12:00:00+00:00",
        "candidate_events": 3,
        "accepted_events": 0,
    }, NOW, source_type="instagram")
    assert snap["health"] == "candidates_rejected"
    assert snap["severity"] == "warning"
    assert snap["publication_blocking"] is False


def test_accepted_not_published_is_critical() -> None:
    snap = acquisition_snapshot({
        "last_success_at": "2026-08-26T12:00:00+00:00",
        "candidate_events": 4,
        "accepted_events": 3,
        "published_events": 2,
    }, NOW, source_type="instagram")
    assert snap["health"] == "accepted_not_published"
    assert snap["severity"] == "critical"
    assert snap["publication_blocking"] is True


def test_legacy_event_funnel_fields_are_normalized() -> None:
    receipt = canonical_acquisition_receipt({
        "refreshed_at": "2026-08-26T12:00:00+00:00",
        "events_detected": 7,
        "events_published": 5,
    })
    assert receipt["receipt_present"] is True
    assert receipt["candidate_events"] == 7
    assert receipt["accepted_events"] == 5
    assert receipt["published_events"] == 5


def test_preservation_only_refresh_does_not_fake_acquisition_success() -> None:
    snap = acquisition_snapshot({
        "refreshed_at": "2026-08-26T17:30:00+00:00",
        "preserved_existing": True,
        "events_detected": 0,
        "events_published": 0,
    }, NOW, source_type="website")
    assert snap["last_attempt_at"] == "2026-08-26T17:30:00+00:00"
    assert snap["last_success_at"] is None
    assert snap["health"] == "freshness_unknown"
    assert snap["severity"] == "warning"
    assert snap["publication_blocking"] is False


def test_explicit_success_can_refresh_preservation_run() -> None:
    snap = acquisition_snapshot({
        "refreshed_at": "2026-08-26T17:30:00+00:00",
        "preserved_existing": True,
        "fetch_ok": True,
        "events_detected": 0,
        "events_published": 0,
    }, NOW, source_type="website")
    assert snap["last_success_at"] == "2026-08-26T17:30:00+00:00"
    assert snap["health"] == "healthy"


def test_missing_receipt_is_observable_but_nonblocking() -> None:
    dataset = {
        "sources": [{"id": "source_a", "name": "A", "kind": "instagram"}],
        "events": [],
        "source_diagnostics": {},
    }
    report = build_city("valparaiso-vina", dataset, {}, NOW)
    row = report["sources"][0]
    assert row["receipt_present"] is False
    assert row["health"] == "freshness_unknown"
    assert row["severity"] == "warning"
    assert row["publication_blocking"] is False
    assert report["summary"]["receipt_missing"] == 1
    assert report["summary"]["critical_sources"] == 0


def test_failed_source_does_not_block_valid_event_from_another_source() -> None:
    dataset = {
        "sources": [
            {"id": "source_a", "name": "A", "kind": "instagram"},
            {"id": "source_b", "name": "B", "kind": "instagram"},
        ],
        "events": [{"id": "b-new", "source_id": "source_b"}],
        "source_diagnostics": {
            "source_a": {
                "last_attempt_at": "2026-08-26T17:00:00+00:00",
                "last_success_at": "2026-08-26T12:00:00+00:00",
                "fetch_ok": False,
            },
            "source_b": {
                "last_attempt_at": "2026-08-26T17:00:00+00:00",
                "last_success_at": "2026-08-26T17:00:00+00:00",
                "fetch_ok": True,
                "raw_items": 1,
                "candidate_events": 1,
                "accepted_events": 1,
                "published_events": 1,
            },
        },
    }
    report = build_city("valparaiso-vina", dataset, {}, NOW)
    rows = {row["id"]: row for row in report["sources"]}
    assert rows["source_a"]["health"] == "fetch_failed"
    assert rows["source_a"]["publication_blocking"] is False
    assert rows["source_b"]["health"] == "healthy"
    assert rows["source_b"]["published_current_count"] == 1
    assert report["publication_blocking_source_ids"] == []
    assert report["critical_source_ids"] == []
    assert report["summary"]["critical_sources"] == 0


def test_deterministic_loss_still_blocks_even_when_other_source_is_healthy() -> None:
    dataset = {
        "sources": [
            {"id": "source_a", "name": "A", "kind": "instagram"},
            {"id": "source_b", "name": "B", "kind": "instagram"},
        ],
        "events": [{"id": "b-new", "source_id": "source_b"}],
        "source_diagnostics": {
            "source_a": {
                "last_success_at": "2026-08-26T17:00:00+00:00",
                "candidate_events": 2,
                "accepted_events": 2,
                "published_events": 1,
            },
            "source_b": {
                "last_success_at": "2026-08-26T17:00:00+00:00",
                "candidate_events": 1,
                "accepted_events": 1,
                "published_events": 1,
            },
        },
    }
    report = build_city("valparaiso-vina", dataset, {}, NOW)
    assert report["publication_blocking_source_ids"] == ["source_a"]
    assert report["critical_source_ids"] == ["source_a"]
    assert report["summary"]["critical_sources"] == 1


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
    test_source_with_events_can_be_stale_without_blocking_publication()
    test_fresh_source_is_healthy()
    test_fetch_failure_is_warning_not_critical()
    test_changed_content_without_candidates_is_warning()
    test_candidates_rejected_is_visible_but_local()
    test_accepted_not_published_is_critical()
    test_legacy_event_funnel_fields_are_normalized()
    test_preservation_only_refresh_does_not_fake_acquisition_success()
    test_explicit_success_can_refresh_preservation_run()
    test_missing_receipt_is_observable_but_nonblocking()
    test_failed_source_does_not_block_valid_event_from_another_source()
    test_deterministic_loss_still_blocks_even_when_other_source_is_healthy()
    test_covered_elsewhere_does_not_raise_stale_warning()
    print("SOURCE_PIPELINE_HEALTH_TESTS_OK")


if __name__ == "__main__":
    main()
