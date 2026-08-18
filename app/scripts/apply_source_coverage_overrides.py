from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUALITY_DIR = ROOT / "app/data/quality"
COVERAGE_PATH = QUALITY_DIR / "source-coverage.json"
EVENT_QUALITY_PATH = QUALITY_DIR / "event-quality.json"
RECOVERY_PATH = QUALITY_DIR / "valpocultura-zero-recovery.json"
MONITOR_PATH = QUALITY_DIR / "priority-zero-monitors.json"
CITY_ID = "valparaiso-vina"

DIAGNOSTIC_ALIASES = {
    "legacy_cineartevina_cl": ("cinearte_vina", "Cine Arte Viña del Mar"),
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_alias_rows(rows: list[dict]) -> list[dict]:
    by_id = {str(row.get("id") or ""): row for row in rows}
    remove: set[str] = set()
    for alias, (canonical, canonical_name) in DIAGNOSTIC_ALIASES.items():
        alias_row = by_id.get(alias)
        if not alias_row:
            continue
        canonical_row = by_id.get(canonical)
        if canonical_row is None:
            alias_row["id"] = canonical
            alias_row["name"] = canonical_name
            by_id[canonical] = alias_row
        else:
            alias_count = int(alias_row.get("current_count") or 0)
            canonical_row["current_count"] = int(canonical_row.get("current_count") or 0) + alias_count
            if canonical_row["current_count"] > 0:
                canonical_row["status"] = "producing"
                canonical_row["severity"] = "ok"
                canonical_row["zero_streak_days"] = 0
                canonical_row["last_nonzero_date"] = alias_row.get("last_nonzero_date") or canonical_row.get("last_nonzero_date")
            canonical_row["name"] = canonical_name
        remove.add(alias)
    return [row for row in rows if str(row.get("id") or "") not in remove]


def recovery_coverage(report: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in report.get("coverage") or []:
        source_id = str(item.get("source_id") or "").strip()
        covered_by = str(item.get("covered_by") or "").strip()
        if not source_id or not covered_by:
            continue
        result.setdefault(source_id, [])
        if covered_by not in result[source_id]:
            result[source_id].append(covered_by)
    return result


def monitored_inactive(report: dict) -> set[str]:
    return {
        str(item.get("id") or "").strip()
        for item in report.get("sources") or []
        if item.get("fetch_ok") is True
        and item.get("verified_inactive") is True
        and item.get("state") == "verified_no_publishable_future"
        and str(item.get("id") or "").strip()
    }


def raw_zero_state(row: dict, thresholds: dict) -> tuple[str, str]:
    zero_streak = int(row.get("zero_streak_days") or 0)
    critical = zero_streak >= int(thresholds.get("zero_critical_days") or 14)
    return ("zero_critical" if critical else "zero_recent", "critical" if critical else "info")


def apply_coverage(coverage: dict, recovered: dict[str, list[str]], verified_zero: set[str] | None = None) -> dict:
    verified_zero = verified_zero or set()
    city = (coverage.get("cities") or {}).get(CITY_ID)
    if not city:
        return coverage
    rows = merge_alias_rows(list(city.get("sources") or []))
    thresholds = coverage.get("thresholds") or {}
    for row in rows:
        source_id = str(row.get("id") or "")
        direct_count = int(row.get("current_count") or 0)
        covered_by = recovered.get(source_id) or []
        row["covered_by_other_sources"] = covered_by
        row["verified_inactive"] = source_id in verified_zero
        if direct_count > 0:
            row["status"] = "producing"
            row["severity"] = "ok"
            row["zero_streak_days"] = 0
            row["verified_inactive"] = False
        elif covered_by:
            row["status"] = "covered_elsewhere"
            row["severity"] = "ok"
            row["zero_streak_days"] = 0
            row["verified_inactive"] = False
        elif source_id in verified_zero:
            row["status"] = "monitored_confirmed_zero"
            row["severity"] = "ok"
            row["zero_streak_days"] = 0
        else:
            row["status"], row["severity"] = raw_zero_state(row, thresholds)
    city["sources"] = rows

    direct_producing = sum(int(row.get("current_count") or 0) > 0 for row in rows)
    covered_elsewhere = sum(
        int(row.get("current_count") or 0) == 0 and row.get("status") == "covered_elsewhere"
        for row in rows
    )
    verified_inactive = sum(
        int(row.get("current_count") or 0) == 0 and row.get("status") == "monitored_confirmed_zero"
        for row in rows
    )
    uncovered = [
        row for row in rows
        if int(row.get("current_count") or 0) == 0
        and row.get("status") not in {"covered_elsewhere", "monitored_confirmed_zero"}
    ]
    summary = city.setdefault("summary", {})
    summary["sources_total"] = len(rows)
    summary["producing_now"] = direct_producing
    summary["direct_zero_now"] = len(rows) - direct_producing
    summary["covered_elsewhere"] = covered_elsewhere
    summary["verified_inactive_zero_now"] = verified_inactive
    summary["zero_now"] = len(uncovered)
    summary["producing_or_covered"] = direct_producing + covered_elsewhere
    summary["producing_covered_or_verified"] = direct_producing + covered_elsewhere + verified_inactive
    summary["zero_3d_or_more"] = sum(
        int(row.get("zero_streak_days") or 0) >= int(thresholds.get("zero_warning_days") or 3)
        for row in uncovered
    )
    summary["zero_7d_or_more"] = sum(
        int(row.get("zero_streak_days") or 0) >= int(thresholds.get("zero_week_days") or 7)
        for row in uncovered
    )
    summary["zero_14d_or_more"] = sum(
        int(row.get("zero_streak_days") or 0) >= int(thresholds.get("zero_critical_days") or 14)
        for row in uncovered
    )
    return coverage


def apply_quality(
    quality: dict,
    coverage: dict,
    recovered: dict[str, list[str]],
    verified_zero: set[str] | None = None,
) -> dict:
    verified_zero = verified_zero or set()
    city = (quality.get("cities") or {}).get(CITY_ID)
    cov_city = (coverage.get("cities") or {}).get(CITY_ID)
    if not city or not cov_city:
        return quality

    source_rows = list(city.get("sources") or [])
    for row in source_rows:
        alias = str(row.get("id") or "")
        if alias in DIAGNOSTIC_ALIASES:
            canonical, canonical_name = DIAGNOSTIC_ALIASES[alias]
            row["id"] = canonical
            row["name"] = canonical_name
    deduped: dict[str, dict] = {}
    for row in source_rows:
        source_id = str(row.get("id") or "")
        existing = deduped.get(source_id)
        if existing is None or int(row.get("count") or 0) > int(existing.get("count") or 0):
            deduped[source_id] = row
    city["sources"] = list(deduped.values())

    cov_rows = list(cov_city.get("sources") or [])
    covered_ids = [
        str(row.get("id") or "")
        for row in cov_rows
        if int(row.get("current_count") or 0) == 0 and row.get("status") == "covered_elsewhere"
    ]
    inactive_ids = [
        str(row.get("id") or "")
        for row in cov_rows
        if int(row.get("current_count") or 0) == 0 and row.get("status") == "monitored_confirmed_zero"
    ]
    priority_ids = [
        str(row.get("id") or "")
        for row in cov_rows
        if int(row.get("current_count") or 0) == 0
        and row.get("status") not in {"covered_elsewhere", "monitored_confirmed_zero"}
    ]
    summary = city.setdefault("summary", {})
    cov_summary = cov_city.get("summary") or {}
    summary["sources_catalogued"] = cov_summary.get("sources_total", summary.get("sources_catalogued", 0))
    summary["sources_producing"] = cov_summary.get("producing_now", summary.get("sources_producing", 0))
    summary["sources_zero"] = cov_summary.get("zero_now", len(priority_ids))
    summary["review_priority_zero_sources"] = len(priority_ids)
    summary["zero_sources_covered_elsewhere"] = len(covered_ids)
    summary["verified_inactive_zero_sources"] = len(inactive_ids)

    gaps = city.setdefault("coverage_gaps", {})
    gaps["review_priority_zero_sources"] = priority_ids
    gaps["zero_sources_covered_elsewhere"] = covered_ids
    gaps["verified_inactive_zero_sources"] = inactive_ids

    covered_lookup = {source_id: recovered.get(source_id) or [] for source_id in covered_ids}
    for row in city["sources"]:
        source_id = str(row.get("id") or "")
        row["covered_by_other_sources"] = covered_lookup.get(source_id, row.get("covered_by_other_sources") or [])
        row["verified_inactive"] = source_id in verified_zero
    return quality


def build() -> tuple[dict, dict, dict]:
    coverage = load(COVERAGE_PATH)
    quality = load(EVENT_QUALITY_PATH)
    recovery = load(RECOVERY_PATH)
    monitor = load(MONITOR_PATH)
    recovered = recovery_coverage(recovery)
    verified_zero = monitored_inactive(monitor)
    coverage = apply_coverage(coverage, recovered, verified_zero)
    quality = apply_quality(quality, coverage, recovered, verified_zero)
    report = {
        "covered_source_ids": sorted(recovered),
        "verified_inactive_source_ids": sorted(verified_zero),
        "valparaiso_summary": ((coverage.get("cities") or {}).get(CITY_ID) or {}).get("summary") or {},
        "review_priority_zero_sources": (
            (((quality.get("cities") or {}).get(CITY_ID) or {}).get("coverage_gaps") or {})
            .get("review_priority_zero_sources") or []
        ),
    }
    return coverage, quality, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply conservative source aliases, official cross-source coverage and verified inactivity to quality diagnostics.")
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
