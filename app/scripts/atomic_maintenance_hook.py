from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUALITY = ROOT / "app/data/quality"


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def load(name: str) -> dict:
    path = QUALITY / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    # This hook is invoked from the final coverage step of the sole automatic
    # publisher. It must never push/commit by itself.
    run("app/scripts/parser_drift_guard.py")
    run("app/scripts/revalidate_upcoming_events.py", "--days", "10", "--max-fetch", "60")
    run("app/scripts/audit_and_recover_images.py", "--max-fetch", "40")

    # Any safe event mutation must be followed by the normal editorial and
    # diagnostic stack so the publication remains internally synchronized.
    run("app/scripts/apply_title_quality_guard.py")
    run("app/scripts/apply_content_quality_guard.py")
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

    revalidation = load("upcoming-revalidation.json")
    drift = load("parser-drift.json")
    image = load("image-audit.json")
    coherence = load("source-coherence.json")
    health = load("maintenance-health.json")
    print(
        "ATOMIC_MAINTENANCE_OK",
        f"revalidated={revalidation.get('updated_events', 0)}",
        f"drift_restored={drift.get('restored_events', 0)}",
        f"images_recovered={image.get('recovered_event_specific_images', 0)}",
        f"image_pct={image.get('event_specific_image_pct_after')}",
        f"coherence={coherence.get('status')}",
        f"health={health.get('status')}",
    )


if __name__ == "__main__":
    main()
