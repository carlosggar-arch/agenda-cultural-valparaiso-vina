from __future__ import annotations

import copy
from datetime import date

import refresh_valpocultura_zero_recovery as recovery
import refresh_valpocultura_zero_recovery_resilient as resilient


def prior_event(source_id: str, end: str = "2099-08-31") -> dict:
    return {
        "id": f"prior-{source_id}",
        "title": f"Previous {source_id}",
        "event_type": "program",
        "schedule": {"start": "2099-08-01", "end": end},
        "location": {"city": "Valparaíso", "venue": source_id},
        "editorial": {"reason": recovery.RECOVERY_REASON, "covered_source_ids": [source_id]},
    }


def test_listing_drift_adds_all_direct_fallbacks() -> None:
    found, original, added = resilient.discover_with_direct_fallback("<html><body>layout changed</body></html>")
    assert original == 0
    assert added == len(resilient.DIRECT_FALLBACK_URLS)
    assert {row["target"]["id"] for row in found} == set(resilient.DIRECT_FALLBACK_URLS)


def test_failed_detail_preserves_only_current_matching_previous_event() -> None:
    today = date(2099, 8, 18)
    keep = prior_event("centex")
    expired = prior_event("estrella_negra_jazz", end="2099-08-10")
    other = prior_event("casa_cultura_valparaiso")
    dataset = {"events": [copy.deepcopy(keep), copy.deepcopy(expired), copy.deepcopy(other)], "counts": {}}
    rows = [
        {
            "target": {"id": "centex"},
            "fetch_ok": False,
            "publishable": False,
        },
        {
            "target": {"id": "estrella_negra_jazz"},
            "fetch_ok": False,
            "publishable": False,
        },
        {
            "target": {"id": "casa_cultura_valparaiso"},
            "fetch_ok": True,
            "publishable": False,
        },
    ]
    updated, stats, failed = resilient.refresh_dataset_preserving_failed(dataset, rows, True, today)
    ids = {item["id"] for item in updated["events"]}
    assert failed == {"centex", "estrella_negra_jazz"}
    assert keep["id"] in ids
    assert expired["id"] not in ids
    assert other["id"] not in ids
    assert stats["preserved_failed_targets"] == 1


def test_successful_expired_probe_does_not_preserve_old_event() -> None:
    today = date(2099, 8, 18)
    old = prior_event("centex")
    dataset = {"events": [copy.deepcopy(old)], "counts": {}}
    rows = [{"target": {"id": "centex"}, "fetch_ok": True, "publishable": False}]
    updated, stats, failed = resilient.refresh_dataset_preserving_failed(dataset, rows, True, today)
    assert failed == set()
    assert updated["events"] == []
    assert stats.get("preserved_failed_targets", 0) == 0


def test_failed_detail_preserves_current_prior_coverage_only() -> None:
    today = date(2099, 8, 18)
    fresh = []
    previous = [
        {"source_id": "centex", "covered_by": "valpocultura", "url": "a", "start": "2099-08-01", "end": "2099-08-31"},
        {"source_id": "estrella_negra_jazz", "covered_by": "valpocultura", "url": "b", "start": "2099-08-01", "end": "2099-08-10"},
        {"source_id": "casa_cultura_valparaiso", "covered_by": "valpocultura", "url": "c", "start": "2099-08-28", "end": "2099-08-28"},
    ]
    merged, count = resilient.merge_failed_prior_coverage(
        fresh, previous, {"centex", "estrella_negra_jazz"}, today
    )
    assert count == 1
    assert [row["source_id"] for row in merged] == ["centex"]


def main() -> None:
    test_listing_drift_adds_all_direct_fallbacks()
    test_failed_detail_preserves_only_current_matching_previous_event()
    test_successful_expired_probe_does_not_preserve_old_event()
    test_failed_detail_preserves_current_prior_coverage_only()
    print("VALPOCULTURA_RESILIENCE_TESTS_OK")


if __name__ == "__main__":
    main()
