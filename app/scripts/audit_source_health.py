from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUALITY = ROOT / "app/data/quality"
FILES = {
    "coverage": QUALITY / "source-coverage.json",
    "quality": QUALITY / "event-quality.json",
    "readiness": QUALITY / "release-readiness.json",
    "balmaceda": QUALITY / "balmaceda-valpo.json",
    "priority_zero": QUALITY / "priority-zero-monitors.json",
    "valpocultura": QUALITY / "valpocultura-zero-recovery.json",
    "high_value": QUALITY / "high-value-sources.json",
}


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_hours(payload: dict, now: datetime) -> float | None:
    generated = parse_time(payload.get("generated_at"))
    if generated is None:
        return None
    return round((now - generated).total_seconds() / 3600.0, 1)


def build(payloads: dict[str, dict], mode: str = "daily", now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    coverage = payloads.get("coverage") or {}
    quality = payloads.get("quality") or {}
    readiness = payloads.get("readiness") or {}
    balmaceda = payloads.get("balmaceda") or {}
    priority = payloads.get("priority_zero") or {}
    valpocultura = payloads.get("valpocultura") or {}
    high_value = payloads.get("high_value") or {}

    cov_city = ((coverage.get("cities") or {}).get("valparaiso-vina") or {})
    cov_summary = cov_city.get("summary") or {}
    q_city = ((quality.get("cities") or {}).get("valparaiso-vina") or {})
    q_summary = q_city.get("summary") or {}
    gaps = q_city.get("coverage_gaps") or {}
    pipeline = q_city.get("pipeline_quality") or {}

    critical: list[str] = []
    warnings: list[str] = []
    observations: list[str] = []

    duplicate_groups = int(pipeline.get("duplicate_groups") or 0)
    unattributed = int(q_summary.get("unattributed_events") or cov_summary.get("unattributed_events") or 0)
    blockers = list(readiness.get("blockers") or [])
    if duplicate_groups:
        critical.append(f"duplicate_groups:{duplicate_groups}")
    if unattributed:
        critical.append(f"unattributed_events:{unattributed}")
    critical.extend(f"release_blocker:{item}" for item in blockers)

    baj_state = str(balmaceda.get("state") or "missing")
    if "fetch_error" in baj_state or "transport" in baj_state or baj_state == "missing":
        warnings.append(f"balmaceda:{baj_state}")
    elif baj_state == "official_site_reachable_discovery_inconclusive":
        warnings.append(f"balmaceda:{baj_state}")
    else:
        observations.append(f"balmaceda:{baj_state}")

    if priority.get("state") not in {"ok", None}:
        warnings.append(f"priority_zero_monitor:{priority.get('state')}")
    if valpocultura.get("fetch_ok") is False:
        warnings.append("valpocultura:fetch_error")

    for row in high_value.get("sources") or []:
        if row.get("state") == "fetch_error":
            warnings.append(f"high_value_fetch_error:{row.get('id')}")

    stale_limit = 36.0 if mode == "daily" else 72.0
    report_ages = {}
    for key in ("coverage", "quality", "readiness", "balmaceda", "priority_zero", "valpocultura"):
        payload = payloads.get(key) or {}
        age = age_hours(payload, now)
        report_ages[key] = age
        if age is None:
            warnings.append(f"missing_generated_at:{key}")
        elif age > stale_limit:
            warnings.append(f"stale_report:{key}:{age}h")

    actionable_zeros = list(gaps.get("review_priority_zero_sources") or [])
    covered = list(gaps.get("zero_sources_covered_elsewhere") or [])
    verified_inactive = list(gaps.get("verified_inactive_zero_sources") or [])
    observations.append(f"actionable_zero_sources:{len(actionable_zeros)}")
    observations.append(f"covered_elsewhere:{len(covered)}")
    observations.append(f"verified_inactive:{len(verified_inactive)}")

    if mode == "weekly":
        if len(actionable_zeros) >= 9:
            warnings.append(f"weekly_actionable_zero_backlog:{len(actionable_zeros)}")
        image_pct = float((q_city.get("field_coverage") or {}).get("image_pct") or 0.0)
        if image_pct < 60.0:
            warnings.append(f"weekly_image_coverage_low:{image_pct}")

    status = "critical" if critical else ("attention" if warnings else "healthy")
    return {
        "schema_version": "1.0.0",
        "generated_at": now.isoformat(timespec="seconds"),
        "mode": mode,
        "status": status,
        "critical": sorted(set(critical)),
        "warnings": sorted(set(warnings)),
        "observations": sorted(set(observations)),
        "summary": {
            "total_events": int(q_summary.get("total_events") or cov_summary.get("total_events") or 0),
            "quality_score": q_summary.get("average_quality_score"),
            "actionable_zero_sources": len(actionable_zeros),
            "covered_elsewhere": len(covered),
            "verified_inactive_zero_sources": len(verified_inactive),
            "duplicate_groups": duplicate_groups,
            "unattributed_events": unattributed,
            "balmaceda_state": baj_state,
        },
        "actionable_zero_source_ids": actionable_zeros,
        "covered_elsewhere_ids": covered,
        "verified_inactive_ids": verified_inactive,
        "report_age_hours": report_ages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit source, coverage and publication health from persisted diagnostics.")
    parser.add_argument("--mode", choices=("daily", "weekly"), default="daily")
    parser.add_argument("--output")
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()

    payloads = {name: load(path) for name, path in FILES.items()}
    report = build(payloads, mode=args.mode)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    if args.fail_on_critical and report["status"] == "critical":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
