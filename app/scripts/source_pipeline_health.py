from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from source_health_contract import acquisition_snapshot

ROOT = Path(__file__).resolve().parents[2]
DATASETS = {
    "valparaiso-vina": ROOT / "agenda_web.json",
    "gijon": ROOT / "app/data/gijon/agenda_web.json",
}
COVERAGE = ROOT / "app/data/quality/source-coverage.json"
DEFAULT_OUTPUT = ROOT / "app/data/quality/source-pipeline-health.json"


def load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def source_id(event: dict) -> str:
    return str(event.get("source_id") or "").strip()


def diagnostics_for(dataset: dict, sid: str) -> dict:
    diagnostics = dataset.get("source_diagnostics") or {}
    if isinstance(diagnostics, dict):
        row = diagnostics.get(sid)
        return row if isinstance(row, dict) else {}
    if isinstance(diagnostics, list):
        for row in diagnostics:
            if isinstance(row, dict) and str(row.get("id") or row.get("source_id") or "") == sid:
                return row
    return {}


def build_city(city_id: str, dataset: dict, coverage_city: dict, now: datetime) -> dict:
    events = dataset.get("events") or []
    counts = Counter(source_id(event) for event in events if source_id(event))
    catalog = {str(row.get("id")): row for row in dataset.get("sources") or [] if row.get("id")}
    coverage_rows = {str(row.get("id")): row for row in coverage_city.get("sources") or [] if row.get("id")}
    source_ids = list(dict.fromkeys([*catalog, *coverage_rows, *counts]))

    rows = []
    for sid in source_ids:
        configured = catalog.get(sid) or {}
        coverage = coverage_rows.get(sid) or {}
        diag = diagnostics_for(dataset, sid)
        role = configured.get("source_role") or configured.get("role") or coverage.get("role")
        source_type = configured.get("kind") or configured.get("source_type") or coverage.get("source_type")
        funnel = acquisition_snapshot(diag, now, source_type=source_type, role=role)
        count = int(counts.get(sid, 0))
        covered_by = list(coverage.get("covered_by_other_sources") or [])
        verified_inactive = bool(coverage.get("verified_inactive"))

        health = funnel["health"]
        severity = funnel["severity"]
        if verified_inactive:
            health, severity = "verified_inactive", "ok"
        elif covered_by and count == 0 and health in {"freshness_unknown", "stale"}:
            health, severity = "covered_elsewhere", "ok"
        elif health == "healthy" and count == 0:
            health, severity = "healthy_zero", "info"

        rows.append({
            "id": sid,
            "name": configured.get("name") or coverage.get("name") or sid,
            "role": role,
            "source_type": source_type,
            "published_current_count": count,
            "covered_by_other_sources": covered_by,
            "verified_inactive": verified_inactive,
            **funnel,
            "health": health,
            "severity": severity,
        })

    status_counts = Counter(row["health"] for row in rows)
    critical = [row["id"] for row in rows if row["severity"] == "critical"]
    warnings = [row["id"] for row in rows if row["severity"] == "warning"]
    return {
        "city_id": city_id,
        "summary": {
            "sources_total": len(rows),
            "healthy": status_counts["healthy"] + status_counts["healthy_zero"] + status_counts["covered_elsewhere"] + status_counts["verified_inactive"],
            "stale": status_counts["stale"],
            "fetch_failed": status_counts["fetch_failed"],
            "content_changed_not_processed": status_counts["content_changed_not_processed"],
            "candidates_rejected": status_counts["candidates_rejected"],
            "accepted_not_published": status_counts["accepted_not_published"],
            "freshness_unknown": status_counts["freshness_unknown"],
            "warning_sources": len(warnings),
            "critical_sources": len(critical),
        },
        "critical_source_ids": critical,
        "warning_source_ids": warnings,
        "sources": rows,
    }


def build(now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    coverage = load(COVERAGE)
    coverage_cities = coverage.get("cities") or {}
    cities = {}
    for city_id, path in DATASETS.items():
        cities[city_id] = build_city(city_id, load(path), coverage_cities.get(city_id) or {}, now)
    critical = sum(city["summary"]["critical_sources"] for city in cities.values())
    warnings = sum(city["summary"]["warning_sources"] for city in cities.values())
    return {
        "schema_version": "1.0.0",
        "generated_at": now.isoformat(timespec="seconds"),
        "status": "critical" if critical else ("attention" if warnings else "healthy"),
        "critical_sources": critical,
        "warning_sources": warnings,
        "cities": cities,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-source acquisition and publication funnel health.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()
    report = build()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if not args.no_write:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text, end="")
    if args.fail_on_critical and report["status"] == "critical":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
