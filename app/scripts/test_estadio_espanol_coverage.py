from __future__ import annotations

from datetime import date

from apply_estadio_espanol_coverage import (
    FINALIZER_PUBLICATION_MODES,
    merged_coverage,
    should_run_atomic_maintenance_hook,
)
from apply_event_derived_source_coverage import event_derived_coverage, merge_recovered


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


def test_event_derived_coverage_is_mergeable_into_atomic_pass() -> None:
    dataset = {
        "events": [
            {
                "title": "Actividad en Casa Prisma",
                "source_id": "otro_agregador_oficial",
                "organizer": "Otro organizador",
                "schedule": {"start": "2026-08-27", "end": "2026-08-27"},
                "location": {"venue_id": "casa_prisma_valpo", "venue": "Casa Prisma Valpo"},
            },
            {
                "title": "Teatro La Paila",
                "source_id": "fuente_municipal",
                "organizer": "Compañía La Paila",
                "schedule": {"start": "2026-08-29", "end": "2026-08-29"},
                "location": {"venue_id": None, "venue": "Teatro La Paila"},
            },
        ]
    }
    derived = event_derived_coverage(dataset, date(2026, 8, 18))
    recovered = merge_recovered(
        {"estadio_espanol_recreo": ["visitavina_estadio_espanol_recovery"]},
        derived,
    )
    assert recovered["estadio_espanol_recreo"] == ["visitavina_estadio_espanol_recovery"]
    assert recovered["casa_prisma_valpo"] == ["otro_agregador_oficial"]
    assert recovered["compania_la_paila"] == ["fuente_municipal"]


# The protected finalizer must never enter the global multi-city maintenance hook.
def test_atomic_maintenance_runs_normally_outside_publication() -> None:
    assert should_run_atomic_maintenance_hook(
        skip_requested=False,
        publication_mode="",
    ) is True


def test_atomic_maintenance_is_blocked_in_every_finalizer_publication_mode() -> None:
    for mode in FINALIZER_PUBLICATION_MODES:
        assert should_run_atomic_maintenance_hook(
            skip_requested=False,
            publication_mode=mode,
        ) is False


def test_explicit_skip_still_blocks_atomic_maintenance() -> None:
    assert should_run_atomic_maintenance_hook(
        skip_requested=True,
        publication_mode="",
    ) is False


def main() -> None:
    test_estadio_is_added_without_erasing_existing_coverage()
    test_event_derived_coverage_is_mergeable_into_atomic_pass()
    test_atomic_maintenance_runs_normally_outside_publication()
    test_atomic_maintenance_is_blocked_in_every_finalizer_publication_mode()
    test_explicit_skip_still_blocks_atomic_maintenance()
    print("ESTADIO_ESPANOL_COVERAGE_TESTS_OK")


if __name__ == "__main__":
    main()
