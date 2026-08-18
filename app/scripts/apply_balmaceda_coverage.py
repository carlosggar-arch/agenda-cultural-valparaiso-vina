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
BALMACEDA_SOURCE_ID = "balmaceda_arte_joven_valpo"
BALMACEDA_CONFIRMED_ZERO_STATES = {
    "official_recent_activity_no_publishable_future_dates",
    "official_site_checked_no_recent_activity_detected",
}


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


def balmaceda_monitored_zero(report: dict) -> set[str]:
    """Return BAJ as a verified current zero only after a complete official check.

    A reachable landing alone is not enough. Every configured landing must have
    succeeded, discovery must have produced at least one detail link, every
    discovered detail page must have been scanned successfully, and the report
    must contain neither a future candidate nor a published recovery event.
    Transport errors and partial scans therefore remain actionable/indeterminate.
    """

    if str(report.get("state") or "") not in BALMACEDA_CONFIRMED_ZERO_STATES:
        return set()
    if int(report.get("future_dated_candidates") or 0) != 0:
        return set()
    if int(report.get("events_published") or 0) != 0:
        return set()

    landings = [item for item in report.get("landings") or [] if isinstance(item, dict)]
    if not landings or not all(item.get("fetch_ok") is True for item in landings):
        return set()

    links = int(report.get("links_discovered") or 0)
    scanned = int(report.get("pages_scanned") or 0)
    failures = report.get("page_fetch_failures") or []
    if links <= 0 or scanned < links or failures:
        return set()

    return {BALMACEDA_SOURCE_ID}


def build() -> tuple[dict, dict, dict]:
    coverage = load(COVERAGE_PATH)
    quality = load(EVENT_QUALITY_PATH)
    report = load(REPORT_PATH)
    monitor = load(MONITOR_PATH)
    recovered = merged_coverage(coverage, report)
    verified_zero = monitored_inactive(monitor) | balmaceda_monitored_zero(report)
    coverage = apply_coverage(coverage, recovered, verified_zero)
    quality = apply_quality(quality, coverage, recovered, verified_zero)
    city = (coverage.get("cities") or {}).get(CITY_ID) or {}
    result = {
        "balmaceda_state": report.get("state"),
        "balmaceda_coverage_applied": BALMACEDA_SOURCE_ID in recovered,
        "balmaceda_monitored_zero": BALMACEDA_SOURCE_ID in verified_zero,
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
