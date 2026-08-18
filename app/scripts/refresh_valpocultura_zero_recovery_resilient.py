from __future__ import annotations

import argparse
import copy
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import refresh_valpocultura_zero_recovery as recovery

# Stable official detail pages. These are fallbacks for discovery only: every
# page is still fetched and parsed by the existing conservative detail parser.
DIRECT_FALLBACK_URLS = {
    "centex": "https://valpocultura.cl/evento/centex-cartelera-agosto/",
    "valparaiso_profundo": "https://valpocultura.cl/evento/valparaiso-profundo-programacion-agosto/",
    "estrella_negra_jazz": "https://valpocultura.cl/evento/club-de-jazz-estrella-negra-cartelera-agosto/",
    "casa_cultura_valparaiso": "https://valpocultura.cl/evento/casa-de-la-cultura-de-valparaiso-luciana-jury-en-chile/",
    "teatro_municipal_valparaiso": "https://valpocultura.cl/evento/teatro-municipal-cartelera-festival-internacional-de-cine-ojo-de-pescado/",
}


def target_by_id() -> dict[str, dict]:
    return {str(target["id"]): target for target in recovery.TARGETS}


def discover_with_direct_fallback(markup: str) -> tuple[list[dict], int, int]:
    found = list(recovery.discover(markup))
    original_count = len(found)
    seen = {str(item["target"]["id"]) for item in found}
    targets = target_by_id()
    for source_id, url in DIRECT_FALLBACK_URLS.items():
        if source_id in seen or source_id not in targets:
            continue
        target = targets[source_id]
        found.append({"target": target, "title": target["name"], "url": url, "direct_fallback": True})
    return found, original_count, len(found) - original_count


def event_is_current(item: dict, today: date) -> bool:
    schedule = item.get("schedule") or {}
    raw = str(schedule.get("end") or schedule.get("start") or "")[:10]
    if not raw:
        return False
    try:
        return date.fromisoformat(raw) >= today
    except ValueError:
        return False


def recovery_target_ids(item: dict) -> set[str]:
    editorial = item.get("editorial") or {}
    return {str(value or "").strip() for value in editorial.get("covered_source_ids") or [] if str(value or "").strip()}


def refresh_dataset_preserving_failed(
    dataset: dict,
    rows: list[dict],
    fetch_ok: bool,
    today: date,
) -> tuple[dict, dict, set[str]]:
    original_events = copy.deepcopy(list(dataset.get("events") or []))
    failed_ids = {
        str(row["target"]["id"])
        for row in rows
        if row.get("fetch_ok") is not True
    }
    updated, stats = recovery.refresh_dataset(dataset, rows, fetch_ok)
    if not fetch_ok or not failed_ids:
        return updated, stats, failed_ids

    preserved = []
    existing_ids = {str(item.get("id") or "") for item in updated.get("events") or []}
    existing_keys = {recovery.event_key(item) for item in updated.get("events") or []}
    for item in original_events:
        if str((item.get("editorial") or {}).get("reason") or "") != recovery.RECOVERY_REASON:
            continue
        if not event_is_current(item, today):
            continue
        if not (recovery_target_ids(item) & failed_ids):
            continue
        if str(item.get("id") or "") in existing_ids or recovery.event_key(item) in existing_keys:
            continue
        preserved.append(item)
        existing_ids.add(str(item.get("id") or ""))
        existing_keys.add(recovery.event_key(item))

    if preserved:
        updated["events"] = sorted(
            list(updated.get("events") or []) + preserved,
            key=lambda item: (str((item.get("schedule") or {}).get("start") or ""), str(item.get("title") or "")),
        )
        events = updated["events"]
        updated["counts"] = {
            "total": len(events),
            "events": sum(item.get("event_type") == "event" for item in events),
            "courses": sum(item.get("event_type") == "course" for item in events),
            "flexible_offers": sum(item.get("event_type") == "flexible_offer" for item in events),
            "programs": sum(item.get("event_type") == "program" for item in events),
        }
        stats = dict(stats)
        stats["preserved_failed_targets"] = len(preserved)
        stats["published"] = int(stats.get("published") or 0) + len(preserved)
        stats["preserved_previous"] = True
    else:
        stats = dict(stats)
        stats["preserved_failed_targets"] = 0
    return updated, stats, failed_ids


def coverage_is_current(item: dict, today: date) -> bool:
    raw = str(item.get("end") or item.get("start") or "")[:10]
    if not raw:
        return False
    try:
        return date.fromisoformat(raw) >= today
    except ValueError:
        return False


def merge_failed_prior_coverage(
    fresh: list[dict],
    previous: list[dict],
    failed_ids: set[str],
    today: date,
) -> tuple[list[dict], int]:
    merged = list(fresh)
    seen = {(str(item.get("source_id") or ""), str(item.get("url") or "")) for item in merged}
    preserved = 0
    for item in previous:
        source_id = str(item.get("source_id") or "")
        key = (source_id, str(item.get("url") or ""))
        if source_id not in failed_ids or key in seen or not coverage_is_current(item, today):
            continue
        merged.append(copy.deepcopy(item))
        seen.add(key)
        preserved += 1
    return merged, preserved


def build() -> tuple[dict, dict]:
    today = datetime.now(ZoneInfo(recovery.TIMEZONE)).date()
    previous_report = recovery.prior_report()
    original_discover = recovery.discover
    original_refresh = recovery.refresh_dataset
    metrics = {"listing_discovered": 0, "direct_fallback_added": 0, "failed_ids": set()}

    def patched_discover(markup: str) -> list[dict]:
        # Call the saved function directly to avoid recursion.
        recovery.discover = original_discover
        try:
            found, original_count, fallback_added = discover_with_direct_fallback(markup)
        finally:
            recovery.discover = patched_discover
        metrics["listing_discovered"] = original_count
        metrics["direct_fallback_added"] = fallback_added
        return found

    def patched_refresh(dataset: dict, rows: list[dict], fetch_ok: bool):
        recovery.refresh_dataset = original_refresh
        try:
            updated, stats, failed_ids = refresh_dataset_preserving_failed(dataset, rows, fetch_ok, today)
        finally:
            recovery.refresh_dataset = patched_refresh
        metrics["failed_ids"] = failed_ids
        return updated, stats

    recovery.discover = patched_discover
    recovery.refresh_dataset = patched_refresh
    try:
        dataset, report = recovery.build(no_write=True)
    finally:
        recovery.discover = original_discover
        recovery.refresh_dataset = original_refresh

    if report.get("fetch_ok") is not True:
        report["listing_discovered"] = metrics["listing_discovered"]
        report["direct_fallback_added"] = metrics["direct_fallback_added"]
        return dataset, report

    failed_ids = set(metrics["failed_ids"])
    coverage, preserved_coverage = merge_failed_prior_coverage(
        list(report.get("coverage") or []),
        list(previous_report.get("coverage") or []),
        failed_ids,
        today,
    )
    report["coverage"] = coverage
    report["active_coverage"] = len(coverage)
    report["listing_discovered"] = metrics["listing_discovered"]
    report["direct_fallback_added"] = metrics["direct_fallback_added"]
    report["detail_fetch_failed_source_ids"] = sorted(failed_ids)
    report["prior_coverage_preserved"] = preserved_coverage

    refresh = dict(report.get("refresh") or {})
    report["refresh"] = refresh
    if metrics["listing_discovered"] == 0 and report["active_coverage"] > 0:
        report["state"] = "listing_drift_direct_fallback_active"
    elif failed_ids and preserved_coverage:
        report["state"] = "partial_preserving_previous"
    elif metrics["direct_fallback_added"]:
        report["state"] = "direct_fallback_checked"
    return dataset, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Valpo Cultura recovery with direct-detail fallback and non-destructive parser-drift handling.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    dataset, report = build()
    if args.no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    recovery.DATASET_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    recovery.REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    recovery.REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
