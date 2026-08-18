from __future__ import annotations

import argparse
import json
from pathlib import Path

from apply_balmaceda_coverage import merged_coverage as merge_existing_coverage
from apply_source_coverage_overrides import (
    CITY_ID,
    COVERAGE_PATH,
    EVENT_QUALITY_PATH,
    apply_coverage,
    apply_quality,
    load,
    recovery_coverage,
    save,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "app/data/quality/visitavina-fonck.json"


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
    recovered = merged_coverage(coverage, report)
    coverage = apply_coverage(coverage, recovered)
    quality = apply_quality(quality, coverage, recovered)
    city = (coverage.get("cities") or {}).get(CITY_ID) or {}
    row = next((item for item in city.get("sources") or [] if item.get("id") == "museo_fonck"), None)
    result = {
        "fonck_state": report.get("state"),
        "fonck_coverage_applied": "museo_fonck" in recovered,
        "fonck_status": (row or {}).get("status"),
        "valparaiso_summary": city.get("summary") or {},
    }
    return coverage, quality, result


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Visita Viña coverage for Museo Fonck without erasing existing source overrides.")
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
