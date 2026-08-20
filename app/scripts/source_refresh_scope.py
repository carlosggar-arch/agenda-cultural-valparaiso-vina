from __future__ import annotations

import argparse
import sys

# Files that can change how official/source data is fetched, reconciled,
# validated or automatically maintained in the public repository.
SOURCE_RUNTIME_PATHS = {
    ".github/workflows/event-pages.yml",
    "app/data/high_value_sources.json",
    "app/data/source-registry.json",
    "app/scripts/fetch_high_value_sources.py",
    "app/scripts/validate_high_value_refresh.py",
    "app/scripts/refresh_museo_maritimo.py",
    "app/scripts/refresh_balmaceda_valpo.py",
    "app/scripts/refresh_balmaceda_valpo_bounded.py",
    "app/scripts/apply_balmaceda_coverage.py",
    "app/scripts/refresh_visitavina_fonck.py",
    "app/scripts/apply_fonck_coverage.py",
    "app/scripts/refresh_visitavina_estadio_espanol.py",
    "app/scripts/apply_estadio_espanol_coverage.py",
    "app/scripts/refresh_portaltickets_editorial.py",
    "app/scripts/validate_portaltickets_editorial.py",
    "app/scripts/refresh_quality_diagnostics.py",
    "app/scripts/refresh_valpocultura_zero_recovery.py",
    "app/scripts/refresh_priority_zero_monitors.py",
    "app/scripts/apply_title_quality_guard.py",
    "app/scripts/apply_content_quality_guard.py",
    "app/scripts/apply_source_coverage_overrides.py",
    "app/scripts/atomic_maintenance_hook.py",
    "app/scripts/event_page_tools.py",
    "app/scripts/revalidate_upcoming_events.py",
    "app/scripts/parser_drift_guard.py",
    "app/scripts/audit_source_coherence.py",
    "app/scripts/audit_and_recover_images.py",
    "app/scripts/source_refresh_scope.py",
}

# Fast deterministic policy tests should run whenever either source runtime or
# its dedicated regression tests change. Network probes are reserved for
# runtime/config/workflow changes only.
SOURCE_TEST_PATHS = {
    "fuentes_publicas.json",
    "agenda_web.json",
    "app/data/gijon/agenda_web.json",
    "app/data/quality/source-coverage.json",
    "app/scripts/validate_source_registry.py",
    "app/scripts/test_source_registry.py",
    "app/scripts/test_high_value_sources.py",
    "app/scripts/test_museo_maritimo.py",
    "app/scripts/test_balmaceda_valpo.py",
    "app/scripts/test_balmaceda_coverage.py",
    "app/scripts/test_visitavina_fonck.py",
    "app/scripts/test_fonck_coverage.py",
    "app/scripts/test_visitavina_estadio_espanol.py",
    "app/scripts/test_estadio_espanol_coverage.py",
    "app/scripts/test_portaltickets_editorial.py",
    "app/scripts/test_valpocultura_zero_recovery.py",
    "app/scripts/test_priority_zero_monitors.py",
    "app/scripts/test_title_quality_guard.py",
    "app/scripts/test_content_quality_guard.py",
    "app/scripts/test_source_coverage_overrides.py",
    "app/scripts/test_maintenance_automation.py",
    "app/scripts/test_source_refresh_scope.py",
}


def normalize_paths(lines: list[str]) -> list[str]:
    return [line.strip().replace("\\", "/") for line in lines if line.strip()]


def classify(paths: list[str]) -> dict[str, bool]:
    normalized = normalize_paths(paths)
    runtime = any(path in SOURCE_RUNTIME_PATHS for path in normalized)
    tests = runtime or any(path in SOURCE_TEST_PATHS for path in normalized)
    return {
        "tests_needed": tests,
        "live_needed": runtime,
        "refresh_needed": runtime,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify changed repository paths for source policy tests, live probes and production refresh."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Changed paths. If omitted, newline-separated paths are read from stdin.",
    )
    args = parser.parse_args()
    paths = args.paths if args.paths else sys.stdin.read().splitlines()
    result = classify(paths)
    for key in ("tests_needed", "live_needed", "refresh_needed"):
        print(f"{key}={'true' if result[key] else 'false'}")


if __name__ == "__main__":
    main()
