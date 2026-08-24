from __future__ import annotations

from source_refresh_scope import classify


def test_ui_only_change_skips_source_work() -> None:
    assert classify(["app/pwa.js", "assets/event-page.css"]) == {"tests_needed": False, "live_needed": False, "refresh_needed": False}


def test_dataset_change_runs_contract_tests_without_external_refresh() -> None:
    assert classify(["agenda_web.json", "app/data/gijon/agenda_web.json"]) == {"tests_needed": True, "live_needed": False, "refresh_needed": False}


def test_registry_change_is_conservative() -> None:
    assert classify(["app/data/source-registry.json"]) == {"tests_needed": True, "live_needed": True, "refresh_needed": True}


def test_source_runtime_change_runs_tests_live_and_refresh() -> None:
    assert classify(["app/scripts/refresh_balmaceda_valpo_bounded.py"]) == {"tests_needed": True, "live_needed": True, "refresh_needed": True}
    assert classify(["app/scripts/cache_official_images.py"]) == {"tests_needed": True, "live_needed": True, "refresh_needed": True}


def test_source_test_change_runs_fast_tests_without_network() -> None:
    assert classify(["app/scripts/test_balmaceda_valpo.py"]) == {"tests_needed": True, "live_needed": False, "refresh_needed": False}
    assert classify(["app/scripts/test_cache_official_images.py"]) == {"tests_needed": True, "live_needed": False, "refresh_needed": False}


def test_workflow_change_is_conservative() -> None:
    assert classify([".github/workflows/publish.yml"]) == {"tests_needed": True, "live_needed": True, "refresh_needed": True}


def test_windows_separators_are_normalized() -> None:
    assert classify([r"app\scripts\refresh_visitavina_fonck.py"])["live_needed"] is True


if __name__ == "__main__":
    test_ui_only_change_skips_source_work()
    test_dataset_change_runs_contract_tests_without_external_refresh()
    test_registry_change_is_conservative()
    test_source_runtime_change_runs_tests_live_and_refresh()
    test_source_test_change_runs_fast_tests_without_network()
    test_workflow_change_is_conservative()
    test_windows_separators_are_normalized()
    print("SOURCE_REFRESH_SCOPE_TESTS_OK")
