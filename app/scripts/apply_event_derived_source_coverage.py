from __future__ import annotations

import argparse
import json
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apply_balmaceda_coverage import merged_coverage as preserve_existing_coverage
from apply_source_coverage_overrides import (
    CITY_ID,
    COVERAGE_PATH,
    EVENT_QUALITY_PATH,
    MONITOR_PATH,
    apply_coverage,
    apply_quality,
    load,
    monitored_inactive,
    save,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
TIMEZONE = "America/Santiago"

# Curated exact aliases only. Title text is intentionally excluded because it
# can mention an organization without the event actually taking place there.
TARGET_RULES = {
    "casa_prisma_valpo": {
        "venue_ids": {"casa_prisma_valpo"},
        "venues": {"casa prisma", "casa prisma valpo"},
        "organizers": {"casa prisma", "casa prisma valpo"},
    },
    "compania_la_paila": {
        "venue_ids": {"compania_la_paila"},
        "venues": {"teatro la paila"},
        "organizers": {"compania la paila", "teatro la paila"},
    },
}


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.casefold().replace("—", " ").replace("–", " ").split())


def event_end_day(item: dict) -> date | None:
    schedule = item.get("schedule") or {}
    raw = str(schedule.get("end") or schedule.get("start") or "")[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def event_matches_rule(item: dict, rule: dict) -> bool:
    location = item.get("location") or {}
    venue_id = str(location.get("venue_id") or "").strip()
    venue = norm(location.get("venue"))
    organizer = norm(item.get("organizer"))
    return (
        venue_id in rule["venue_ids"]
        or venue in rule["venues"]
        or organizer in rule["organizers"]
    )


def event_derived_coverage(dataset: dict, today: date) -> dict[str, list[str]]:
    recovered: dict[str, list[str]] = {}
    for item in dataset.get("events") or []:
        end_day = event_end_day(item)
        if not end_day or end_day < today:
            continue
        provider = str(item.get("source_id") or "").strip()
        if not provider:
            continue
        for target_id, rule in TARGET_RULES.items():
            if provider == target_id or not event_matches_rule(item, rule):
                continue
            recovered.setdefault(target_id, [])
            if provider not in recovered[target_id]:
                recovered[target_id].append(provider)
    return recovered


def merge_recovered(base: dict[str, list[str]], extra: dict[str, list[str]]) -> dict[str, list[str]]:
    result = {key: list(values) for key, values in base.items()}
    for source_id, providers in extra.items():
        result.setdefault(source_id, [])
        for provider in providers:
            if provider not in result[source_id]:
                result[source_id].append(provider)
    return result


def build() -> tuple[dict, dict, dict]:
    coverage = load(COVERAGE_PATH)
    quality = load(EVENT_QUALITY_PATH)
    monitor = load(MONITOR_PATH)
    dataset = load(DATASET_PATH)
    today = datetime.now(ZoneInfo(TIMEZONE)).date()

    existing = preserve_existing_coverage(coverage, {})
    derived = event_derived_coverage(dataset, today)
    recovered = merge_recovered(existing, derived)
    verified_zero = monitored_inactive(monitor)

    coverage = apply_coverage(coverage, recovered, verified_zero)
    quality = apply_quality(quality, coverage, recovered, verified_zero)
    city = (coverage.get("cities") or {}).get(CITY_ID) or {}
    rows = {str(row.get("id") or ""): row for row in city.get("sources") or []}
    report = {
        "derived_cross_source_coverage": derived,
        "casa_prisma_status": (rows.get("casa_prisma_valpo") or {}).get("status"),
        "la_paila_status": (rows.get("compania_la_paila") or {}).get("status"),
        "valparaiso_summary": city.get("summary") or {},
    }
    return coverage, quality, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive conservative cross-source coverage from future events already present in the canonical Valpo dataset.")
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
