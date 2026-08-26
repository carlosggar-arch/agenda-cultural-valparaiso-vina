from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apply_event_derived_source_coverage import (
    DATASET_PATH,
    event_derived_coverage,
    merge_recovered,
)
from apply_fonck_coverage import merged_coverage as merge_existing_coverage
from apply_source_coverage_overrides import (
    CITY_ID,
    COVERAGE_PATH,
    EVENT_QUALITY_PATH,
    MONITOR_PATH,
    apply_coverage,
    apply_quality,
    load,
    monitored_inactive,
    recovery_coverage,
    save,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "app/data/quality/visitavina-estadio-espanol.json"
TARGET_SOURCE_ID = "estadio_espanol_recreo"
TIMEZONE = "America/Santiago"
MAINTENANCE_HOOK_PATH = "app/scripts/atomic_maintenance_hook.py"
FINALIZER_PUBLICATION_MODES = frozenset(
    {"manual", "push", "schedule", "rematerialize", "verification"}
)


def merged_coverage(coverage: dict, report: dict) -> dict[str, list[str]]:
    recovered = merge_existing_coverage(coverage, {})
    for source_id, providers in recovery_coverage(report).items():
        recovered.setdefault(source_id, [])
        for provider in providers:
            if provider not in recovered[source_id]:
                recovered[source_id].append(provider)
    return recovered


def build() -> tuple[dict, dict, dict]:
    coverage = load(COVERAGE_PATH)
    quality = load(EVENT_QUALITY_PATH)
    report = load(REPORT_PATH)
    monitor = load(MONITOR_PATH)
    dataset = load(DATASET_PATH)

    recovered = merged_coverage(coverage, report)
    derived = event_derived_coverage(dataset, datetime.now(ZoneInfo(TIMEZONE)).date())
    recovered = merge_recovered(recovered, derived)
    verified_zero = monitored_inactive(monitor)

    coverage = apply_coverage(coverage, recovered, verified_zero)
    quality = apply_quality(quality, coverage, recovered, verified_zero)
    city = (coverage.get("cities") or {}).get(CITY_ID) or {}
    row = next((item for item in city.get("sources") or [] if item.get("id") == TARGET_SOURCE_ID), None)
    result = {
        "estadio_state": report.get("state"),
        "estadio_coverage_applied": TARGET_SOURCE_ID in recovered,
        "estadio_status": (row or {}).get("status"),
        "derived_cross_source_coverage": derived,
        "verified_inactive_source_ids": sorted(verified_zero),
        "valparaiso_summary": city.get("summary") or {},
    }
    return coverage, quality, result


def should_run_atomic_maintenance_hook(
    *,
    skip_requested: bool,
    publication_mode: str | None = None,
) -> bool:
    """Keep global maintenance out of city-scoped finalizer transactions.

    The protected finalizer binds PUBLICATION_MODE before it invokes this script.
    Global maintenance intentionally touches shared multi-city outputs, so it must
    not run inside a publication transaction for one selected city. Outside the
    finalizer, the historical maintenance behavior remains unchanged.
    """
    mode = (
        publication_mode
        if publication_mode is not None
        else os.environ.get("PUBLICATION_MODE", "")
    )
    normalized_mode = str(mode or "").strip().casefold()
    return not skip_requested and normalized_mode not in FINALIZER_PUBLICATION_MODES


def run_atomic_maintenance_hook() -> None:
    subprocess.run(
        [sys.executable, MAINTENANCE_HOOK_PATH],
        cwd=ROOT,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Estadio Español plus conservative event-derived coverage inside the atomic coverage pass without erasing verified-inactivity overrides.")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument(
        "--skip-maintenance-hook",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    coverage, quality, report = build()
    if args.no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    save(COVERAGE_PATH, coverage)
    save(EVENT_QUALITY_PATH, quality)
    print(json.dumps(report, ensure_ascii=False))
    if should_run_atomic_maintenance_hook(skip_requested=args.skip_maintenance_hook):
        run_atomic_maintenance_hook()
    else:
        print(
            "ESTADIO_GLOBAL_MAINTENANCE_SKIPPED "
            f"publication_mode={os.environ.get('PUBLICATION_MODE') or 'none'} "
            f"explicit={str(args.skip_maintenance_hook).lower()}"
        )


if __name__ == "__main__":
    main()
