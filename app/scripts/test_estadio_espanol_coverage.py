from __future__ import annotations

from apply_estadio_espanol_coverage import merged_coverage


def test_estadio_is_added_without_erasing_existing_coverage() -> None:
    coverage = {
        "cities": {
            "valparaiso-vina": {
                "sources": [
                    {"id": "centex", "covered_by_other_sources": ["valpocultura"]},
                    {"id": "museo_fonck", "covered_by_other_sources": ["visitavina_fonck_recovery"]},
                    {"id": "estadio_espanol_recreo", "covered_by_other_sources": []},
                ]
            }
        }
    }
    report = {
        "coverage": [{
            "source_id": "estadio_espanol_recreo",
            "covered_by": "visitavina_estadio_espanol_recovery",
        }]
    }
    recovered = merged_coverage(coverage, report)
    assert recovered["centex"] == ["valpocultura"]
    assert recovered["museo_fonck"] == ["visitavina_fonck_recovery"]
    assert recovered["estadio_espanol_recreo"] == ["visitavina_estadio_espanol_recovery"]


def main() -> None:
    test_estadio_is_added_without_erasing_existing_coverage()
    print("ESTADIO_ESPANOL_COVERAGE_TESTS_OK")


if __name__ == "__main__":
    main()
