from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
EVENT_PAGES = (WORKFLOWS / "event-pages.yml").read_text(encoding="utf-8")
FALLBACK = (WORKFLOWS / "compose-valpo-dataset.yml").read_text(encoding="utf-8")
CONTENT_QUALITY = (WORKFLOWS / "content-quality-guard.yml").read_text(encoding="utf-8")
CROSS_SOURCE = (WORKFLOWS / "cross-source-reconciliation.yml").read_text(encoding="utf-8")
CLOUDFLARE_SYNC = (WORKFLOWS / "sync-cloudflare-preview.yml").read_text(encoding="utf-8")
MAINTENANCE_WORKFLOW = (WORKFLOWS / "maintenance-automation.yml").read_text(encoding="utf-8")
ESTADIO_APPLIER = (ROOT / "app/scripts/apply_estadio_espanol_coverage.py").read_text(encoding="utf-8")
MAINTENANCE_HOOK = (ROOT / "app/scripts/atomic_maintenance_hook.py").read_text(encoding="utf-8")

FINALIZER_MARKER = "agenda-cultural-core/.github/workflows/finalize-public-agenda.yml"
MAINTENANCE_STEPS = [
    "app/scripts/parser_drift_guard.py",
    "app/scripts/revalidate_upcoming_events.py",
    "app/scripts/schedule_authority_guard.py",
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


def git_add_blocks(text: str) -> list[str]:
    """Return complete shell git-add commands, including continued lines."""
    lines = text.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if "git add" not in line:
            index += 1
            continue
        block = [line]
        while block[-1].rstrip().endswith("\\") and index + 1 < len(lines):
            index += 1
            block.append(lines[index])
        blocks.append("\n".join(block))
        index += 1
    return blocks


def stages_root_valpo_dataset(text: str) -> bool:
    """Match only the root Valpo dataset, never Gijon's nested agenda_web.json."""
    for block in git_add_blocks(text):
        tokens = block.replace("\\", " ").split()
        if "agenda_web.json" in tokens:
            return True
    return False


def pushes_public_main(text: str) -> bool:
    """Recognize direct writes to main while allowing deployment-branch syncs."""
    compact = text.replace("'", "").replace('"', "")
    markers = (
        "git push origin HEAD:main",
        "git push origin main",
        "git push --force origin HEAD:main",
        "git push --force-with-lease origin HEAD:main",
    )
    return any(marker in compact for marker in markers)


def secondary_public_main_writers() -> list[str]:
    offenders: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if stages_root_valpo_dataset(text) and pushes_public_main(text):
            offenders.append(path.name)
    return offenders


def assert_read_only_workflow(text: str, name: str) -> None:
    assert "contents: read" in text, f"{name} must have read-only contents permission"
    assert "contents: write" not in text, f"{name} must not request contents: write"
    assert not pushes_public_main(text), f"{name} must not push to public main"


def main() -> None:
    # Permanent pages are validation-only; the protected cross-repo finalizer owns publication.
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

    # Former local writers remain available as diagnostics/fallback validators, never writers.
    fallback_triggers = FALLBACK.split("permissions:", 1)[0]
    assert "push:" not in fallback_triggers, "Fallback composer must not auto-run on push"
    assert "workflow_dispatch:" in FALLBACK, "Fallback composer must remain manually runnable"
    for name, workflow in (
        ("compose-valpo-dataset.yml", FALLBACK),
        ("content-quality-guard.yml", CONTENT_QUALITY),
        ("cross-source-reconciliation.yml", CROSS_SOURCE),
    ):
        assert_read_only_workflow(workflow, name)

    # Cloudflare is deliberately allowed to synchronize its deployment branch, but never main.
    assert "git push origin HEAD:cloudflare-preview" in CLOUDFLARE_SYNC
    assert not pushes_public_main(CLOUDFLARE_SYNC)

    offenders = secondary_public_main_writers()
    assert not offenders, (
        "PUBLIC_DATASET_SECONDARY_MAIN_WRITERS: " + ", ".join(offenders)
        + ". Root agenda_web.json may only be written by " + FINALIZER_MARKER
    )

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
    assert "SCHEDULE_AUTHORITY_FETCH_BUDGET" in MAINTENANCE_HOOK
    assert "IMAGE_FETCH_BUDGET" in MAINTENANCE_HOOK
    assert '"app/data/quality/schedule-authority.json"' in MAINTENANCE_HOOK
    assert "git commit" not in MAINTENANCE_HOOK
    assert "git push" not in MAINTENANCE_HOOK
    assert "stage_outputs()" in MAINTENANCE_HOOK

    print(
        "ATOMIC_PUBLICATION_CONTRACT_OK "
        "protected_writer=agenda-cultural-core/finalize-public-agenda.yml "
        "secondary_public_main_writers=0"
    )


if __name__ == "__main__":
    main()
