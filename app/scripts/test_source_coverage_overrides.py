from __future__ import annotations

import copy

from apply_source_coverage_overrides import apply_coverage, apply_quality, recovery_coverage


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
    return coverage, quality, recovery


def test_alias_and_cross_source_states() -> None:
    coverage, quality, recovery = fixtures()
    gijon_before = copy.deepcopy(coverage["cities"]["gijon"])
    recovered = recovery_coverage(recovery)
    apply_coverage(coverage, recovered)
    apply_quality(quality, coverage, recovered)

    rows = {row["id"]: row for row in coverage["cities"]["valparaiso-vina"]["sources"]}
    assert "legacy_cineartevina_cl" not in rows
    assert rows["cinearte_vina"]["current_count"] == 16
    assert rows["cinearte_vina"]["status"] == "producing"
    assert rows["centex"]["status"] == "covered_elsewhere"
    assert rows["centex"]["covered_by_other_sources"] == ["valpocultura"]
    assert rows["casa_cultura_valparaiso"]["status"] == "covered_elsewhere"
    assert rows["balmaceda_arte_joven_valpo"]["status"] == "zero_recent"

    summary = coverage["cities"]["valparaiso-vina"]["summary"]
    assert summary["sources_total"] == 4
    assert summary["producing_now"] == 1
    assert summary["direct_zero_now"] == 3
    assert summary["covered_elsewhere"] == 2
    assert summary["zero_now"] == 1
    assert summary["producing_or_covered"] == 3

    qcity = quality["cities"]["valparaiso-vina"]
    assert qcity["summary"]["zero_sources_covered_elsewhere"] == 2
    assert qcity["summary"]["review_priority_zero_sources"] == 1
    assert qcity["coverage_gaps"]["review_priority_zero_sources"] == ["balmaceda_arte_joven_valpo"]
    assert set(qcity["coverage_gaps"]["zero_sources_covered_elsewhere"]) == {"centex", "casa_cultura_valparaiso"}
    assert qcity["sources"][0]["id"] == "cinearte_vina"
    assert coverage["cities"]["gijon"] == gijon_before


def main() -> None:
    test_alias_and_cross_source_states()
    print("SOURCE_COVERAGE_OVERRIDES_TESTS_OK")


if __name__ == "__main__":
    main()
