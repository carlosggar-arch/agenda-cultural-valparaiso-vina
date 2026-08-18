from __future__ import annotations

import argparse
import json
from pathlib import Path

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
REPORT_PATH = ROOT / "app/data/quality/balmaceda-valpo.json"


def merged_coverage(coverage: dict, report: dict) -> dict[str, list[str]]:
    recovered: dict[str, list[str]] = {}
    city = (coverage.get("cities") or {}).get(CITY_ID) or {}
    for row in city.get("sources") or []:
        source_id = str(row.get("id") or "").strip()
        if not source_id:
            continue
        for covered_by in row.get("covered_by_other_sources") or []:
            value = str(covered_by or "").strip()
            if value:
                recovered.setdefault(source_id, [])
                if value not in recovered[source_id]:
                    recovered[source_id].append(value)
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
    recovered = merged_coverage(coverage, report)
    verified_zero = monitored_inactive(monitor)
    coverage = apply_coverage(coverage, recovered, verified_zero)
    quality = apply_quality(quality, coverage, recovered, verified_zero)
    city = (coverage.get("cities") or {}).get(CITY_ID) or {}
    result = {
        "balmaceda_state": report.get("state"),
        "balmaceda_coverage_applied": "balmaceda_arte_joven_valpo" in recovered,
        "verified_inactive_source_ids": sorted(verified_zero),
        "valparaiso_summary": city.get("summary") or {},
    }
    return coverage, quality, result


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Balmaceda official-source coverage without erasing existing recovery or verified-inactivity overrides.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    coverage, quality, report = build()
    if args.no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    save(COVERAGE_PATH, coverage)
    save(EVENT_QUALITY_PATH, quality)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
