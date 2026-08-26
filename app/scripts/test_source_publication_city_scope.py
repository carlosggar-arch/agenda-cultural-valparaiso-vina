from __future__ import annotations

from apply_estadio_espanol_coverage import (
    FINALIZER_PUBLICATION_MODES,
    should_run_atomic_maintenance_hook,
)
from normalize_schedule_display import DATASET_PATH, GIJON_DATASET_PATH, dataset_targets
from validate_high_value_refresh import DATASETS, selected_datasets


def test_valpo_schedule_normalization_never_selects_gijon_implicitly() -> None:
    assert dataset_targets(DATASET_PATH) == [DATASET_PATH]
    assert GIJON_DATASET_PATH not in dataset_targets(DATASET_PATH)
    assert GIJON_DATASET_PATH in dataset_targets(
        DATASET_PATH,
        include_sibling_cities=True,
    )


def test_high_value_refresh_is_valpo_only_by_default() -> None:
    assert selected_datasets() == [("valparaiso", DATASETS["valparaiso"])]
    assert all(name != "gijon" for name, _ in selected_datasets())
    assert {name for name, _ in selected_datasets(all_cities=True)} == {
        "valparaiso",
        "gijon",
    }


def test_finalizer_publication_modes_never_launch_global_atomic_maintenance() -> None:
    for mode in FINALIZER_PUBLICATION_MODES:
        assert not should_run_atomic_maintenance_hook(
            skip_requested=False,
            publication_mode=mode,
        ), mode


def test_standalone_maintenance_contract_remains_explicit() -> None:
    assert should_run_atomic_maintenance_hook(
        skip_requested=False,
        publication_mode="",
    )
    assert not should_run_atomic_maintenance_hook(
        skip_requested=True,
        publication_mode="",
    )


def main() -> None:
    test_valpo_schedule_normalization_never_selects_gijon_implicitly()
    test_high_value_refresh_is_valpo_only_by_default()
    test_finalizer_publication_modes_never_launch_global_atomic_maintenance()
    test_standalone_maintenance_contract_remains_explicit()
    print("PUBLICATION_CITY_SCOPE_CONTRACT_OK")


if __name__ == "__main__":
    main()
