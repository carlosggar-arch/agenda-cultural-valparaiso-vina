from __future__ import annotations

import argparse
import copy
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from event_page_tools import (
    best_matching_event,
    date_part,
    event_detail_url,
    event_status,
    extract_event_candidates,
    fetch,
    location_from_candidate,
    offer_from_candidate,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
REPORT_PATH = ROOT / "app/data/quality/upcoming-revalidation.json"
TIMEZONE = "America/Santiago"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def event_end_day(item: dict) -> date | None:
    schedule = item.get("schedule") or {}
    raw = str(schedule.get("end") or schedule.get("start") or "")[:10]
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def event_start_day(item: dict) -> date | None:
    raw = str((item.get("schedule") or {}).get("start") or "")[:10]
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def is_upcoming(item: dict, today: date, days: int) -> bool:
    start = event_start_day(item)
    end = event_end_day(item)
    if not start or not end:
        return False
    return end >= today and start <= today + timedelta(days=days)


def pretty_schedule(start: str, end: str | None) -> str:
    def pretty(value: str) -> str:
        text = str(value or "")
        if "T" not in text:
            return text[:10]
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.strftime("%d-%m-%Y %H:%M")
    if not end or end == start:
        return pretty(start)
    return f"{pretty(start)} – {pretty(end)}"


def apply_candidate(item: dict, candidate: dict, verified_at: str) -> list[str]:
    changes: list[str] = []
    schedule = item.setdefault("schedule", {})
    status = item.setdefault("public_status", {})
    location = item.setdefault("location", {})
    price = item.setdefault("price", {})

    candidate_status = event_status(candidate)
    if candidate_status == "cancelled" and status.get("cancelled") is not True:
        status["cancelled"] = True
        status["advisory_text"] = "Evento marcado como cancelado en la ficha oficial."
        changes.append("cancelled")
    elif candidate_status in {"postponed", "rescheduled"}:
        advisory = "Evento marcado como aplazado/reprogramado en la ficha oficial; revisa la nueva fecha antes de asistir."
        if status.get("advisory_text") != advisory:
            status["advisory_text"] = advisory
            changes.append(candidate_status)

    new_start = str(candidate.get("startDate") or "").strip()
    new_end = str(candidate.get("endDate") or "").strip()
    if new_start and date_part(new_start):
        old_start = str(schedule.get("start") or "")
        old_end = str(schedule.get("end") or "")
        if new_start != old_start:
            schedule["start"] = new_start
            changes.append("start")
        if new_end and date_part(new_end) and new_end != old_end:
            schedule["end"] = new_end
            changes.append("end")
        if "start" in changes or "end" in changes:
            schedule["display_text"] = pretty_schedule(str(schedule.get("start") or new_start), str(schedule.get("end") or "") or None)
            schedule["start_confidence"] = "official_revalidation"
            if schedule.get("end"):
                schedule["end_confidence"] = "official_revalidation"

    venue, address = location_from_candidate(candidate)
    if venue and venue != str(location.get("venue") or "").strip():
        location["venue"] = venue
        changes.append("venue")
    if address and address != str(location.get("address") or "").strip():
        location["address"] = address
        changes.append("address")

    amount, currency, sold_out = offer_from_candidate(candidate)
    if amount is not None:
        if price.get("min_amount") != amount or price.get("max_amount") != amount:
            price["min_amount"] = amount
            price["max_amount"] = amount
            price["is_free"] = amount == 0
            price["currency"] = currency or price.get("currency") or "CLP"
            price["display_text"] = "Gratis" if amount == 0 else f"${amount:,.0f}".replace(",", ".")
            status["price_confirmed"] = True
            changes.append("price")
    if sold_out is True and status.get("sold_out") is not True:
        status["sold_out"] = True
        changes.append("sold_out")

    item["last_verified_at"] = verified_at
    status["last_verified_at"] = verified_at
    if changes:
        editorial = item.setdefault("editorial", {})
        editorial["last_automatic_revalidation_at"] = verified_at
        editorial["automatic_revalidation_fields"] = sorted(set(changes))
    return sorted(set(changes))


def build(dataset: dict, today: date, days: int = 10, max_fetch: int = 60) -> tuple[dict, dict]:
    dataset = copy.deepcopy(dataset)
    events = dataset.get("events") or []
    targets = [item for item in events if is_upcoming(item, today, days)]
    verified_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    report_rows = []
    fetched = 0
    changed = 0
    review = 0
    errors = 0
    skipped = 0

    for item in targets:
        url = event_detail_url(item)
        if not url:
            skipped += 1
            report_rows.append({"id": item.get("id"), "state": "no_event_specific_structured_url"})
            continue
        if fetched >= max_fetch:
            skipped += 1
            report_rows.append({"id": item.get("id"), "state": "fetch_budget_exhausted", "url": url})
            continue
        fetched += 1
        ok, status_code, markup, error = fetch(url)
        if not ok:
            errors += 1
            report_rows.append({"id": item.get("id"), "state": "fetch_error", "url": url, "http_status": status_code, "error": error})
            continue
        candidate, score = best_matching_event(item, extract_event_candidates(markup))
        if not candidate:
            review += 1
            report_rows.append({"id": item.get("id"), "state": "no_confident_event_jsonld_match", "url": url, "match_score": round(score, 3)})
            continue
        fields = apply_candidate(item, candidate, verified_at)
        if fields:
            changed += 1
            state = "updated"
        else:
            state = "verified_unchanged"
        report_rows.append({"id": item.get("id"), "state": state, "url": url, "match_score": round(score, 3), "fields": fields})

    report = {
        "schema_version": "1.0.0",
        "generated_at": verified_at,
        "window_days": days,
        "targets": len(targets),
        "fetched": fetched,
        "updated_events": changed,
        "review_needed": review,
        "fetch_errors": errors,
        "skipped": skipped,
        "rows": report_rows,
    }
    return dataset, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Conservatively revalidate near-term Valpo events from event-specific structured pages.")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--max-fetch", type=int, default=60)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    dataset = load(DATASET_PATH)
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    updated, report = build(dataset, today=today, days=max(1, args.days), max_fetch=max(1, args.max_fetch))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.no_write:
        save(DATASET_PATH, updated)
        save(REPORT_PATH, report)


if __name__ == "__main__":
    main()
