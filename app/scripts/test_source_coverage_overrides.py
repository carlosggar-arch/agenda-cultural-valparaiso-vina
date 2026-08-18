from __future__ import annotations

import copy

from apply_source_coverage_overrides import apply_coverage, apply_quality, monitored_inactive, recovery_coverage


def fixtures():
    coverage = {
        "thresholds": {"zero_warning_days": 3, "zero_week_days": 7, "zero_critical_days": 14},
        "cities": {
            "valparaiso-vina": {
                "summary": {},
                "sources": [
                    {"id": "cinearte_vina", "name": "Cine Arte Viña del Mar", "current_count": 0, "status": "zero_recent", "severity": "info", "zero_streak_days": 1},
                    {"id": "legacy_cineartevina_cl", "name": "cineartevina.cl", "current_count": 16, "status": "producing", "severity": "ok", "zero_streak_days": 0, "last_nonzero_date": "2099-01-01"},
                    {"id": "centex", "name": "CENTEX", "current_count": 0, "status": "zero_recent", "severity": "info", "zero_streak_days": 2},
                    {"id": "casa_cultura_valparaiso", "name": "Casa de la Cultura", "current_count": 0, "status": "zero_recent", "severity": "info", "zero_streak_days": 2},
                    {"id": "balmaceda_arte_joven_valpo", "name": "BAJ", "current_count": 0, "status": "zero_recent", "severity": "info", "zero_streak_days": 2},
                    {"id": "sala_teatro_ipa", "name": "Sala Teatro IPA", "current_count": 0, "status": "zero_recent", "severity": "info", "zero_streak_days": 2},
                ],
            },
            "gijon": {"summary": {"zero_now": 9}, "sources": [{"id": "agenda_gijon", "current_count": 0, "status": "zero_recent"}]},
        },
    }
    quality = {
        "cities": {
            "valparaiso-vina": {
                "summary": {},
                "sources": [{"id": "legacy_cineartevina_cl", "name": "cineartevina.cl", "count": 16, "covered_by_other_sources": []}],
                "coverage_gaps": {"review_priority_zero_sources": [], "zero_sources_covered_elsewhere": []},
            },
            "gijon": {"summary": {"sources_zero": 9}, "sources": [], "coverage_gaps": {}},
        }
    }
    recovery = {
        "coverage": [
            {"source_id": "centex", "covered_by": "valpocultura"},
            {"source_id": "casa_cultura_valparaiso", "covered_by": "valpocultura"},
        ]
    }
    monitor = {
        "sources": [
            {
                "id": "balmaceda_arte_joven_valpo",
                "fetch_ok": True,
                "state": "verified_no_publishable_future",
                "verified_inactive": True,
            },
            {
                "id": "sala_teatro_ipa",
                "fetch_ok": True,
                "state": "future_detected",
                "verified_inactive": False,
            },
        ]
    }
    return coverage, quality, recovery, monitor


def test_alias_cross_source_and_verified_inactive_states() -> None:
    coverage, quality, recovery, monitor = fixtures()
    gijon_before = copy.deepcopy(coverage["cities"]["gijon"])
    recovered = recovery_coverage(recovery)
    inactive = monitored_inactive(monitor)
    apply_coverage(coverage, recovered, inactive)
    apply_quality(quality, coverage, recovered, inactive)

    rows = {row["id"]: row for row in coverage["cities"]["valparaiso-vina"]["sources"]}
    assert "legacy_cineartevina_cl" not in rows
    assert rows["cinearte_vina"]["current_count"] == 16
    assert rows["cinearte_vina"]["status"] == "producing"
    assert rows["centex"]["status"] == "covered_elsewhere"
    assert rows["centex"]["covered_by_other_sources"] == ["valpocultura"]
    assert rows["casa_cultura_valparaiso"]["status"] == "covered_elsewhere"
    assert rows["balmaceda_arte_joven_valpo"]["status"] == "monitored_confirmed_zero"
    assert rows["balmaceda_arte_joven_valpo"]["verified_inactive"] is True
    assert rows["sala_teatro_ipa"]["status"] == "zero_recent"

    summary = coverage["cities"]["valparaiso-vina"]["summary"]
    assert summary["sources_total"] == 5
    assert summary["producing_now"] == 1
    assert summary["direct_zero_now"] == 4
    assert summary["covered_elsewhere"] == 2
    assert summary["verified_inactive_zero_now"] == 1
    assert summary["zero_now"] == 1
    assert summary["producing_or_covered"] == 3
    assert summary["producing_covered_or_verified"] == 4

    qcity = quality["cities"]["valparaiso-vina"]
    assert qcity["summary"]["zero_sources_covered_elsewhere"] == 2
    assert qcity["summary"]["verified_inactive_zero_sources"] == 1
    assert qcity["summary"]["review_priority_zero_sources"] == 1
    assert qcity["coverage_gaps"]["review_priority_zero_sources"] == ["sala_teatro_ipa"]
    assert qcity["coverage_gaps"]["verified_inactive_zero_sources"] == ["balmaceda_arte_joven_valpo"]
    assert set(qcity["coverage_gaps"]["zero_sources_covered_elsewhere"]) == {"centex", "casa_cultura_valparaiso"}
    assert qcity["sources"][0]["id"] == "cinearte_vina"
    assert coverage["cities"]["gijon"] == gijon_before


def main() -> None:
    test_alias_cross_source_and_verified_inactive_states()
    print("SOURCE_COVERAGE_OVERRIDES_TESTS_OK")


if __name__ == "__main__":
    main()
