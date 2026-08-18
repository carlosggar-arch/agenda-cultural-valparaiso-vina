from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENT_PAGES = (ROOT / ".github/workflows/event-pages.yml").read_text(encoding="utf-8")
FALLBACK = (ROOT / ".github/workflows/compose-valpo-dataset.yml").read_text(encoding="utf-8")
MAINTENANCE_WORKFLOW = (ROOT / ".github/workflows/maintenance-automation.yml").read_text(encoding="utf-8")
ESTADIO_APPLIER = (ROOT / "app/scripts/apply_estadio_espanol_coverage.py").read_text(encoding="utf-8")
MAINTENANCE_HOOK = (ROOT / "app/scripts/atomic_maintenance_hook.py").read_text(encoding="utf-8")

REQUIRED_MAIN_STEPS = [
    "python app/scripts/refresh_museo_maritimo.py",
    "python app/scripts/refresh_balmaceda_valpo_bounded.py",
    "python app/scripts/refresh_visitavina_fonck.py",
    "python app/scripts/refresh_visitavina_estadio_espanol.py",
    "python app/scripts/refresh_portaltickets_editorial.py",
    "python app/scripts/refresh_valpocultura_zero_recovery.py",
    "python app/scripts/refresh_priority_zero_monitors.py",
    "python app/scripts/apply_title_quality_guard.py",
    "python app/scripts/apply_content_quality_guard.py",
    "python app/scripts/refresh_quality_diagnostics.py",
    "python app/scripts/apply_source_coverage_overrides.py",
    "python app/scripts/apply_balmaceda_coverage.py",
    "python app/scripts/apply_fonck_coverage.py",
    "python app/scripts/apply_estadio_espanol_coverage.py",
]

MAINTENANCE_STEPS = [
    "app/scripts/parser_drift_guard.py",
    "app/scripts/revalidate_upcoming_events.py",
    "app/scripts/audit_and_recover_images.py",
    "app/scripts/audit_source_coherence.py",
]

REQUIRED_MAIN_PUSH_PATHS = [
    '      - "agenda_web.json"',
    '      - "app/data/gijon/agenda_web.json"',
    '      - "scripts/generate_event_pages.py"',
    '      - "scripts/stage31_site_generator.py"',
    '      - "app/data/high_value_sources.json"',
    '      - "app/scripts/atomic_maintenance_hook.py"',
    '      - "app/scripts/source_refresh_scope.py"',
    '      - ".github/workflows/event-pages.yml"',
]

FORBIDDEN_MAIN_PUSH_PATHS = [
    '      - "assets/event-page.css"',
    '      - "assets/event-page.js"',
    '      - "assets/accessibility.css"',
    '      - "assets/city-page.css"',
    '      - "assets/event-permalink.css"',
    '      - "assets/web-event-enhancements.js"',
    '      - "app/event-detail.js"',
    '      - "app/pwa.js"',
    '      - "app/service-worker.js"',
    '      - "app/stage31-accessibility-seo.js"',
    '      - "app/stage31-accessibility.css"',
    '      - "tests/test_stage31.py"',
    '      - "app/scripts/test_high_value_sources.py"',
    '      - "app/scripts/test_source_refresh_scope.py"',
]


def main_push_block() -> str:
    start = EVENT_PAGES.index("  push:\n")
    end = EVENT_PAGES.index("  workflow_dispatch:\n", start)
    return EVENT_PAGES[start:end]


def main() -> None:
    positions = []
    for marker in REQUIRED_MAIN_STEPS:
        index = EVENT_PAGES.find(marker)
        assert index >= 0, f"Missing atomic publication step: {marker}"
        positions.append(index)
    assert positions == sorted(positions), "Supplement steps are not in the intended publication order"
    commit_index = EVENT_PAGES.find('git commit -m "Actualiza fuentes, diagnósticos y fichas permanentes"')
    assert commit_index > max(positions), "Publication commit happens before supplemental composition finishes"
    assert "app/data/quality/visitavina-fonck.json" in EVENT_PAGES
    assert "app/data/quality/visitavina-estadio-espanol.json" in EVENT_PAGES
    assert "app/data/quality/balmaceda-valpo.json" in EVENT_PAGES
    assert "app/data/quality/content-quality.json" in EVENT_PAGES

    # Main push should wake the publisher only for data/generator/source-runtime
    # changes. UI assets and test-only changes are validated on PR and must not
    # re-run the publication workflow after merge.
    push_block = main_push_block()
    for marker in REQUIRED_MAIN_PUSH_PATHS:
        assert marker in push_block, f"Required main push trigger missing: {marker.strip()}"
    for marker in FORBIDDEN_MAIN_PUSH_PATHS:
        assert marker not in push_block, f"Redundant main push trigger returned: {marker.strip()}"
    for line in push_block.splitlines():
        stripped = line.strip().strip('- ').strip('"')
        if stripped.startswith("app/scripts/test_"):
            raise AssertionError(f"Test-only path must not trigger main publication: {stripped}")

    # All fallback or specialist workflows must remain non-automatic writers.
    assert "push:" not in FALLBACK.split("permissions:", 1)[0], "Fallback composer must not auto-run on push"
    assert "workflow_dispatch:" in FALLBACK, "Fallback composer must remain manually runnable"
    maintenance_triggers = MAINTENANCE_WORKFLOW.split("permissions:", 1)[0]
    assert "push:" not in maintenance_triggers, "Maintenance guard must not be a second automatic writer"
    assert "workflow_run:" not in maintenance_triggers, "Maintenance guard must not write after another workflow"
    assert "schedule:" not in maintenance_triggers, "Maintenance guard must not own a second schedule"
    assert "contents: read" in MAINTENANCE_WORKFLOW
    assert "git commit" not in MAINTENANCE_WORKFLOW
    assert "git push" not in MAINTENANCE_WORKFLOW

    # The automatic maintenance layers are reached from the final coverage step
    # that already belongs to Permanent event pages, preserving one writer.
    assert "run_atomic_maintenance_hook()" in ESTADIO_APPLIER
    assert "--skip-maintenance-hook" in ESTADIO_APPLIER
    maintenance_positions = []
    for marker in MAINTENANCE_STEPS:
        index = MAINTENANCE_HOOK.find(marker)
        assert index >= 0, f"Missing atomic maintenance layer: {marker}"
        maintenance_positions.append(index)
    assert maintenance_positions == sorted(maintenance_positions), "Maintenance layers run in an unexpected order"
    assert "REVALIDATION_FETCH_BUDGET" in MAINTENANCE_HOOK
    assert "IMAGE_FETCH_BUDGET" in MAINTENANCE_HOOK
    assert "git commit" not in MAINTENANCE_HOOK
    assert "git push" not in MAINTENANCE_HOOK
    assert "stage_outputs()" in MAINTENANCE_HOOK

    print("ATOMIC_PUBLICATION_CONTRACT_OK")


if __name__ == "__main__":
    main()
