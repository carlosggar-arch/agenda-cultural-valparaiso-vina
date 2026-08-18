from __future__ import annotations

from source_refresh_scope import classify


def test_ui_only_change_skips_source_work() -> None:
    result = classify(["app/pwa.js", "assets/event-page.css"])
    assert result == {"tests_needed": False, "live_needed": False, "refresh_needed": False}


def test_dataset_only_change_skips_external_refresh() -> None:
    result = classify(["agenda_web.json", "app/data/gijon/agenda_web.json"])
    assert result == {"tests_needed": False, "live_needed": False, "refresh_needed": False}


def test_source_runtime_change_runs_tests_live_and_refresh() -> None:
    result = classify(["app/scripts/refresh_balmaceda_valpo_bounded.py"])
    assert result == {"tests_needed": True, "live_needed": True, "refresh_needed": True}


def test_source_test_change_runs_fast_tests_without_network() -> None:
    result = classify(["app/scripts/test_balmaceda_valpo.py"])
    assert result == {"tests_needed": True, "live_needed": False, "refresh_needed": False}


def test_workflow_change_is_conservative() -> None:
    result = classify([".github/workflows/event-pages.yml"])
    assert result == {"tests_needed": True, "live_needed": True, "refresh_needed": True}


def test_windows_separators_are_normalized() -> None:
    result = classify([r"app\scripts\refresh_visitavina_fonck.py"])
    assert result["live_needed"] is True


def main() -> None:
    test_ui_only_change_skips_source_work()
    test_dataset_only_change_skips_external_refresh()
    test_source_runtime_change_runs_tests_live_and_refresh()
    test_source_test_change_runs_fast_tests_without_network()
    test_workflow_change_is_conservative()
    test_windows_separators_are_normalized()
    print("SOURCE_REFRESH_SCOPE_TESTS_OK")


if __name__ == "__main__":
    main()
