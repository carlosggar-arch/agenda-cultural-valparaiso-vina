from __future__ import annotations

import argparse
import copy
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from event_page_tools import (
    best_matching_event,
    event_detail_url,
    extract_event_candidates,
    fetch,
    image_url_from_candidate,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
REPORT_PATH = ROOT / "app/data/quality/image-audit.json"
TIMEZONE = "America/Santiago"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def venue_key(item: dict) -> tuple[str, str] | None:
    location = item.get("location") or {}
    city = norm(location.get("city"))
    venue = norm(location.get("venue"))
    if not city or not venue or venue == city or venue.startswith(("online", "sitio web")):
        return None
    if venue.endswith(" " + city):
        venue = venue[: -(len(city) + 1)].strip()
    return (city, venue) if venue else None


def has_image(item: dict) -> bool:
    return bool(str((item.get("image") or {}).get("url") or "").strip())


def event_end_day(item: dict) -> date | None:
    schedule = item.get("schedule") or {}
    raw = str(schedule.get("end") or schedule.get("start") or "")[:10]
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def build(dataset: dict, today: date, max_fetch: int = 40) -> tuple[dict, dict]:
    dataset = copy.deepcopy(dataset)
    events = dataset.get("events") or []
    current = [item for item in events if (event_end_day(item) or date.min) >= today]
    missing = [item for item in current if not has_image(item)]

    existing_venue_images: dict[tuple[str, str], list[str]] = {}
    for item in current:
        key = venue_key(item)
        url = str((item.get("image") or {}).get("url") or "").strip()
        if key and url:
            existing_venue_images.setdefault(key, [])
            if url not in existing_venue_images[key]:
                existing_venue_images[key].append(url)

    rows = []
    fetched = recovered = fetch_errors = no_match = 0
    verified_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")

    for item in missing:
        key = venue_key(item)
        representative = bool(key and existing_venue_images.get(key))
        url = event_detail_url(item)
        if not url:
            rows.append({"id": item.get("id"), "state": "no_event_specific_url", "representative_available": representative})
            continue
        if fetched >= max_fetch:
            rows.append({"id": item.get("id"), "state": "fetch_budget_exhausted", "representative_available": representative})
            continue
        fetched += 1
        ok, http_status, markup, error = fetch(url)
        if not ok:
            fetch_errors += 1
            rows.append({"id": item.get("id"), "state": "fetch_error", "url": url, "http_status": http_status, "error": error, "representative_available": representative})
            continue
        candidate, score = best_matching_event(item, extract_event_candidates(markup))
        if not candidate:
            no_match += 1
            rows.append({"id": item.get("id"), "state": "no_confident_event_match", "url": url, "match_score": round(score, 3), "representative_available": representative})
            continue
        image_url = image_url_from_candidate(candidate, markup)
        if not image_url:
            rows.append({"id": item.get("id"), "state": "matched_but_no_event_image", "url": url, "match_score": round(score, 3), "representative_available": representative})
            continue

        item["image"] = {
            "url": image_url,
            "alt": str(item.get("title") or "").strip() or None,
            "source": "official_event_page",
            "relevance": "event_specific",
        }
        item.setdefault("editorial", {})["image_recovered_at"] = verified_at
        item["editorial"]["image_recovery_method"] = "matched_event_jsonld_or_og"
        recovered += 1
        if key:
            existing_venue_images.setdefault(key, [])
            if image_url not in existing_venue_images[key]:
                existing_venue_images[key].append(image_url)
        rows.append({"id": item.get("id"), "state": "recovered", "url": url, "match_score": round(score, 3), "image_url": image_url})

    current_after = [item for item in events if (event_end_day(item) or date.min) >= today]
    missing_after = [item for item in current_after if not has_image(item)]
    representative_after = sum(bool(venue_key(item) and existing_venue_images.get(venue_key(item))) for item in missing_after)
    report = {
        "schema_version": "1.0.0",
        "generated_at": verified_at,
        "current_events": len(current),
        "events_with_images_before": len(current) - len(missing),
        "missing_images_before": len(missing),
        "fetched_pages": fetched,
        "recovered_event_specific_images": recovered,
        "fetch_errors": fetch_errors,
        "no_confident_match": no_match,
        "missing_images_after": len(missing_after),
        "representative_fallback_available_after": representative_after,
        "event_specific_image_pct_after": round(100.0 * (len(current_after) - len(missing_after)) / len(current_after), 1) if current_after else 0.0,
        "rows": rows,
    }
    return dataset, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit missing event images and conservatively recover event-specific official images.")
    parser.add_argument("--max-fetch", type=int, default=40)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    dataset = load(DATASET_PATH)
    updated, report = build(dataset, datetime.now(ZoneInfo(TIMEZONE)).date(), max_fetch=max(1, args.max_fetch))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.no_write:
        save(DATASET_PATH, updated)
        save(REPORT_PATH, report)


if __name__ == "__main__":
    main()
