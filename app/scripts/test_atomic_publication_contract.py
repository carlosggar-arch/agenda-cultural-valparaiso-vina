from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENT_PAGES = (ROOT / ".github/workflows/event-pages.yml").read_text(encoding="utf-8")
FALLBACK = (ROOT / ".github/workflows/compose-valpo-dataset.yml").read_text(encoding="utf-8")
MAINTENANCE_WORKFLOW = (ROOT / ".github/workflows/maintenance-automation.yml").read_text(encoding="utf-8")
ESTADIO_APPLIER = (ROOT / "app/scripts/apply_estadio_espanol_coverage.py").read_text(encoding="utf-8")
MAINTENANCE_HOOK = (ROOT / "app/scripts/atomic_maintenance_hook.py").read_text(encoding="utf-8")

FINALIZER_MARKER = "agenda-cultural-core/.github/workflows/finalize-public-agenda.yml"
MAINTENANCE_STEPS = [
    "app/scripts/parser_drift_guard.py",
    "app/scripts/revalidate_upcoming_events.py",
    "app/scripts/audit_and_recover_images.py",
    "app/scripts/audit_source_coherence.py",
]

REQUIRED_VALIDATION_PUSH_PATHS = [
    '      - "agenda_web.json"',
    '      - "app/data/gijon/agenda_web.json"',
    '      - "scripts/generate_event_pages.py"',
    '      - "scripts/stage31_site_generator.py"',
    '      - ".github/workflows/event-pages.yml"',
]

FORBIDDEN_VALIDATION_PUSH_PATHS = [
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
]


def push_block() -> str:
    start = EVENT_PAGES.index("  push:\n")
    end = EVENT_PAGES.index("  workflow_dispatch:\n", start)
    return EVENT_PAGES[start:end]


def main() -> None:
    assert FINALIZER_MARKER in EVENT_PAGES
    assert "permissions:\n  contents: read" in EVENT_PAGES
    assert "git commit" not in EVENT_PAGES
    assert "git push" not in EVENT_PAGES
    triggers = EVENT_PAGES.split("permissions:", 1)[0]
    assert "schedule:" not in triggers
    assert "workflow_run:" not in triggers

    assert "python scripts/stage31_site_generator.py --check" in EVENT_PAGES
    assert "python scripts/stage31_site_generator.py" in EVENT_PAGES
    assert "test -d evento/valparaiso" in EVENT_PAGES
    assert "test -d evento/gijon" in EVENT_PAGES
    assert "test -f gijon/index.html" in EVENT_PAGES
    assert "MULTICITY_PERMANENT_PAGES_VALIDATION_OK" in EVENT_PAGES
    assert "READ_ONLY_GENERATION_SCOPE_OK" in EVENT_PAGES

    current_push = push_block()
    for marker in REQUIRED_VALIDATION_PUSH_PATHS:
        assert marker in current_push, f"Required validation push trigger missing: {marker.strip()}"
    for marker in FORBIDDEN_VALIDATION_PUSH_PATHS:
        assert marker not in current_push, f"Redundant validation push trigger returned: {marker.strip()}"

    assert "push:" not in FALLBACK.split("permissions:", 1)[0], "Fallback composer must not auto-run on push"
    assert "workflow_dispatch:" in FALLBACK, "Fallback composer must remain manually runnable"
    maintenance_triggers = MAINTENANCE_WORKFLOW.split("permissions:", 1)[0]
    assert "push:" not in maintenance_triggers, "Maintenance guard must not be a second automatic writer"
    assert "workflow_run:" not in maintenance_triggers, "Maintenance guard must not write after another workflow"
    assert "schedule:" not in maintenance_triggers, "Maintenance guard must not own a second schedule"
    assert "contents: read" in MAINTENANCE_WORKFLOW
    assert "git commit" not in MAINTENANCE_WORKFLOW
    assert "git push" not in MAINTENANCE_WORKFLOW

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

    print("ATOMIC_PUBLICATION_CONTRACT_OK protected_writer=agenda-cultural-core/finalize-public-agenda.yml")


if __name__ == "__main__":
    main()
