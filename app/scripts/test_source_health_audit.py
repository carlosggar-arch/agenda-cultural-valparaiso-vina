from __future__ import annotations

from datetime import datetime, timezone

from audit_source_health import build


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)


def payloads() -> dict:
    generated = "2026-08-18T11:00:00+00:00"
    return {
        "coverage": {
            "generated_at": generated,
            "cities": {"valparaiso-vina": {"summary": {"total_events": 165, "unattributed_events": 0}}},
        },
        "quality": {
            "generated_at": generated,
            "cities": {
                "valparaiso-vina": {
                    "summary": {"total_events": 165, "average_quality_score": 92.1, "unattributed_events": 0},
                    "field_coverage": {"image_pct": 63.0},
                    "coverage_gaps": {
                        "review_priority_zero_sources": ["balmaceda_arte_joven_valpo"],
                        "zero_sources_covered_elsewhere": ["centex"],
                        "verified_inactive_zero_sources": ["sala_teatro_ipa", "teatro_la_peste"],
                    },
                    "pipeline_quality": {"duplicate_groups": 0},
                }
            },
        },
        "readiness": {"generated_at": generated, "blockers": []},
        "balmaceda": {"generated_at": generated, "state": "official_site_checked_no_recent_activity_detected"},
        "priority_zero": {"generated_at": generated, "state": "ok"},
        "valpocultura": {"generated_at": generated, "fetch_ok": True},
        "high_value": {"generated_at": generated, "sources": []},
    }


def test_healthy_daily_audit() -> None:
    report = build(payloads(), mode="daily", now=NOW)
    assert report["status"] == "healthy", report
    assert report["summary"]["actionable_zero_sources"] == 1
    assert report["summary"]["verified_inactive_zero_sources"] == 2


def test_balmaceda_transport_failure_is_attention_not_critical() -> None:
    data = payloads()
    data["balmaceda"]["state"] = "official_site_fetch_error"
    report = build(data, mode="daily", now=NOW)
    assert report["status"] == "attention"
    assert "balmaceda:official_site_fetch_error" in report["warnings"]
    assert report["critical"] == []


def test_duplicates_are_critical() -> None:
    data = payloads()
    data["quality"]["cities"]["valparaiso-vina"]["pipeline_quality"]["duplicate_groups"] = 2
    report = build(data, mode="daily", now=NOW)
    assert report["status"] == "critical"
    assert "duplicate_groups:2" in report["critical"]


def test_weekly_audit_flags_large_zero_backlog_and_low_images() -> None:
    data = payloads()
    data["quality"]["cities"]["valparaiso-vina"]["coverage_gaps"]["review_priority_zero_sources"] = [f"s{i}" for i in range(9)]
    data["quality"]["cities"]["valparaiso-vina"]["field_coverage"]["image_pct"] = 53.3
    report = build(data, mode="weekly", now=NOW)
    assert report["status"] == "attention"
    assert "weekly_actionable_zero_backlog:9" in report["warnings"]
    assert "weekly_image_coverage_low:53.3" in report["warnings"]


def main() -> None:
    test_healthy_daily_audit()
    test_balmaceda_transport_failure_is_attention_not_critical()
    test_duplicates_are_critical()
    test_weekly_audit_flags_large_zero_backlog_and_low_images()
    print("SOURCE_HEALTH_AUDIT_TESTS_OK")


if __name__ == "__main__":
    main()
