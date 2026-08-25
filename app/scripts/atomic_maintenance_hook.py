from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUALITY = ROOT / "app/data/quality"
REVALIDATION_FETCH_BUDGET = 20
SCHEDULE_AUTHORITY_FETCH_BUDGET = 20
IMAGE_FETCH_BUDGET = 10
IMAGE_CACHE_FETCH_BUDGET = 10
MAINTENANCE_OUTPUTS = (
    "app/data/quality/parser-drift-state.json",
    "app/data/quality/parser-drift.json",
    "app/data/quality/upcoming-revalidation.json",
    "app/data/quality/schedule-authority.json",
    "app/data/quality/image-audit.json",
    "app/data/quality/image-cache.json",
    "app/data/quality/source-coherence.json",
    "app/data/quality/maintenance-health.json",
)


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def load(name: str) -> dict:
    path = QUALITY / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def stage_outputs() -> None:
    # The hook never commits or pushes. It only stages its persisted state so
    # the sole atomic publication commit includes the maintenance diagnostics.
    candidates = [
        *MAINTENANCE_OUTPUTS,
        "agenda_web.json", "app/data/gijon/agenda_web.json",
        "app/assets/event-images",
    ]
    existing = [value for value in candidates if (ROOT / value).exists()]
    subprocess.run(["git", "add", *existing], cwd=ROOT, check=True)


def main() -> None:
    # This hook is invoked from the final coverage step of the sole automatic
    # publisher. Network work is deliberately bounded; anything not visited in
    # one pass remains eligible for the next daily publication.
    run("app/scripts/parser_drift_guard.py")
    run(
        "app/scripts/revalidate_upcoming_events.py",
        "--days", "10",
        "--max-fetch", str(REVALIDATION_FETCH_BUDGET),
    )

    # Generic JSON-LD revalidation is useful, but event sources can expose
    # several clocks for doors, approximate show time, or other practical
    # information. Source-specific authority runs afterwards so the final
    # public schedule is taken only from an unambiguous official schedule
    # field and explicit structured timestamps are never reduced to dates.
    run(
        "app/scripts/schedule_authority_guard.py",
        "--days", "120",
        "--max-fetch", str(SCHEDULE_AUTHORITY_FETCH_BUDGET),
    )

    run(
        "app/scripts/audit_and_recover_images.py",
        "--max-fetch", str(IMAGE_FETCH_BUDGET),
    )
    run(
        "app/scripts/cache_official_images.py",
        "--max-fetch", str(IMAGE_CACHE_FETCH_BUDGET),
    )

    # Any safe event mutation must be followed by the normal editorial and
    # diagnostic stack so the publication remains internally synchronized.
    run("app/scripts/apply_title_quality_guard.py")
    run("app/scripts/apply_content_quality_guard.py")

    # Re-materialize the shared category authority after any source/editorial mutation.
    run("scripts/materialize_public_categories.py")
    run("app/scripts/refresh_quality_diagnostics.py")
    run("app/scripts/apply_source_coverage_overrides.py")
    run("app/scripts/apply_balmaceda_coverage.py")
    run("app/scripts/apply_fonck_coverage.py")

    # Re-apply Estadio Español + event-derived coverage after diagnostics were
    # regenerated. The flag prevents recursive invocation of this hook.
    run("app/scripts/apply_estadio_espanol_coverage.py", "--skip-maintenance-hook")

    run("app/scripts/audit_source_coherence.py", "--fail-on-critical")
    run(
        "app/scripts/audit_source_health.py",
        "--mode", "daily",
        "--output", "app/data/quality/maintenance-health.json",
        "--fail-on-critical",
    )
    stage_outputs()

    revalidation = load("upcoming-revalidation.json")
    schedule_authority = load("schedule-authority.json")
    drift = load("parser-drift.json")
    image = load("image-audit.json")
    image_cache = load("image-cache.json")
    coherence = load("source-coherence.json")
    health = load("maintenance-health.json")
    print(
        "ATOMIC_MAINTENANCE_OK",
        f"revalidated={revalidation.get('updated_events', 0)}",
        f"schedule_authority={schedule_authority.get('updated_events', 0)}",
        f"drift_restored={drift.get('restored_events', 0)}",
        f"images_recovered={image.get('recovered_event_specific_images', 0)}",
        f"images_cached={image_cache.get('stored', 0)}",
        f"image_pct={image.get('event_specific_image_pct_after')}",
        f"coherence={coherence.get('status')}",
        f"health={health.get('status')}",
        f"revalidation_budget={REVALIDATION_FETCH_BUDGET}",
        f"schedule_authority_budget={SCHEDULE_AUTHORITY_FETCH_BUDGET}",
        f"image_budget={IMAGE_FETCH_BUDGET}",
        f"image_cache_budget={IMAGE_CACHE_FETCH_BUDGET}",
    )


if __name__ == "__main__":
    main()
