from __future__ import annotations

from apply_fonck_coverage import merged_coverage


def test_fonck_is_added_without_erasing_other_coverage() -> None:
    coverage = {
        "cities": {
            "valparaiso-vina": {
                "sources": [
                    {"id": "centex", "covered_by_other_sources": ["valpocultura"]},
                    {"id": "balmaceda_arte_joven_valpo", "covered_by_other_sources": ["balmaceda_arte_joven_valpo_official"]},
                    {"id": "museo_fonck", "covered_by_other_sources": []},
                ]
            }
        }
    }
    report = {
        "coverage": [{
            "source_id": "museo_fonck",
            "covered_by": "visitavina_fonck_recovery",
        }]
    }
    recovered = merged_coverage(coverage, report)
    assert recovered["centex"] == ["valpocultura"]
    assert recovered["balmaceda_arte_joven_valpo"] == ["balmaceda_arte_joven_valpo_official"]
    assert recovered["museo_fonck"] == ["visitavina_fonck_recovery"]


def main() -> None:
    test_fonck_is_added_without_erasing_other_coverage()
    print("FONCK_COVERAGE_TESTS_OK")


if __name__ == "__main__":
    main()
