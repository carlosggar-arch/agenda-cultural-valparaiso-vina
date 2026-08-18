from __future__ import annotations

from apply_balmaceda_coverage import balmaceda_monitored_zero, merged_coverage


def test_existing_recovery_is_preserved_and_balmaceda_added() -> None:
    coverage = {
        "cities": {
            "valparaiso-vina": {
                "sources": [
                    {"id": "centex", "covered_by_other_sources": ["valpocultura"]},
                    {"id": "balmaceda_arte_joven_valpo", "covered_by_other_sources": []},
                ]
            }
        }
    }
    report = {
        "coverage": [
            {
                "source_id": "balmaceda_arte_joven_valpo",
                "covered_by": "balmaceda_arte_joven_valpo_official",
            }
        ]
    }
    recovered = merged_coverage(coverage, report)
    assert recovered["centex"] == ["valpocultura"]
    assert recovered["balmaceda_arte_joven_valpo"] == ["balmaceda_arte_joven_valpo_official"]


def complete_zero_report() -> dict:
    return {
        "state": "official_site_checked_no_recent_activity_detected",
        "future_dated_candidates": 0,
        "events_published": 0,
        "landings": [
            {"url": "https://www.balmacedartejoven.cl/", "fetch_ok": True},
            {"url": "https://www.balmacedartejoven.cl/sedes/sede-valparaiso/", "fetch_ok": True},
        ],
        "links_discovered": 2,
        "pages_scanned": 2,
        "page_fetch_failures": [],
    }


def test_complete_official_zero_is_monitored() -> None:
    assert balmaceda_monitored_zero(complete_zero_report()) == {"balmaceda_arte_joven_valpo"}


def test_partial_transport_or_scan_never_confirms_zero() -> None:
    landing_failure = complete_zero_report()
    landing_failure["landings"][1]["fetch_ok"] = False
    assert balmaceda_monitored_zero(landing_failure) == set()

    detail_failure = complete_zero_report()
    detail_failure["pages_scanned"] = 1
    detail_failure["page_fetch_failures"] = [{"url": "detail", "error": "timeout"}]
    assert balmaceda_monitored_zero(detail_failure) == set()


def test_future_evidence_never_confirms_zero() -> None:
    report = complete_zero_report()
    report["future_dated_candidates"] = 1
    assert balmaceda_monitored_zero(report) == set()

    report = complete_zero_report()
    report["events_published"] = 1
    assert balmaceda_monitored_zero(report) == set()


def main() -> None:
    test_existing_recovery_is_preserved_and_balmaceda_added()
    test_complete_official_zero_is_monitored()
    test_partial_transport_or_scan_never_confirms_zero()
    test_future_evidence_never_confirms_zero()
    print("BALMACEDA_COVERAGE_TESTS_OK")


if __name__ == "__main__":
    main()
