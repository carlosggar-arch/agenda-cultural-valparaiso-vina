from __future__ import annotations

from apply_balmaceda_coverage import merged_coverage


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


def main() -> None:
    test_existing_recovery_is_preserved_and_balmaceda_added()
    print("BALMACEDA_COVERAGE_TESTS_OK")


if __name__ == "__main__":
    main()
