from __future__ import annotations

import argparse
import copy
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from event_page_tools import fetch

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
COVERAGE_PATH = ROOT / "app/data/quality/source-coverage.json"
CATALOG_PATH = ROOT / "fuentes_publicas.json"
STATE_PATH = ROOT / "app/data/quality/parser-drift-state.json"
REPORT_PATH = ROOT / "app/data/quality/parser-drift.json"
TIMEZONE = "America/Santiago"
SOCIAL_HOSTS = {"instagram.com", "www.instagram.com", "facebook.com", "www.facebook.com", "linktr.ee", "www.linktr.ee"}


def load(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def event_end_day(item: dict) -> date | None:
    schedule = item.get("schedule") or {}
    raw = str(schedule.get("end") or schedule.get("start") or "")[:10]
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def event_key(item: dict) -> tuple[str, str, str]:
    return (
        norm(item.get("title")),
        str((item.get("schedule") or {}).get("start") or "")[:16],
        norm((item.get("location") or {}).get("city")),
    )


def recalc_counts(dataset: dict) -> None:
    events = dataset.get("events") or []
    dataset["counts"] = {
        "total": len(events),
        "events": sum(item.get("event_type") == "event" for item in events),
        "courses": sum(item.get("event_type") == "course" for item in events),
        "flexible_offers": sum(item.get("event_type") == "flexible_offer" for item in events),
        "programs": sum(item.get("event_type") == "program" for item in events),
    }


def catalog_urls(catalog: dict) -> dict[str, str]:
    result = {}
    for row in catalog.get("sources") or []:
        name = norm(row.get("name"))
        url = str(row.get("website_url") or "").strip()
        if name and url:
            result[name] = url
    return result


def is_structured_web_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.netloc.casefold() not in SOCIAL_HOSTS


def grouped_events(dataset: dict) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for item in dataset.get("events") or []:
        sid = str(item.get("source_id") or "").strip()
        if sid:
            groups.setdefault(sid, []).append(copy.deepcopy(item))
    return groups


def build(dataset: dict, coverage: dict, catalog: dict, state: dict, today: date) -> tuple[dict, dict, dict]:
    dataset = copy.deepcopy(dataset)
    state = copy.deepcopy(state) if state else {"schema_version": "1.0.0", "sources": {}}
    state.setdefault("sources", {})
    groups = grouped_events(dataset)
    city = ((coverage.get("cities") or {}).get("valparaiso-vina") or {})
    rows = city.get("sources") or []
    urls = catalog_urls(catalog)
    now = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    known_keys = {event_key(item) for item in dataset.get("events") or []}
    restored = []
    suspected = []
    checked = 0

    for row in rows:
        sid = str(row.get("id") or "").strip()
        if not sid:
            continue
        current_count = int(row.get("current_count") or 0)
        if current_count > 0 and groups.get(sid):
            new_events = groups[sid]
            prior = state["sources"].get(sid) or {}
            old_keys = sorted(event_key(item) for item in prior.get("events") or [])
            new_keys = sorted(event_key(item) for item in new_events)
            if int(prior.get("last_good_count") or 0) != current_count or old_keys != new_keys:
                state["sources"][sid] = {
                    "name": row.get("name"),
                    "last_good_at": now,
                    "last_good_count": current_count,
                    "events": new_events,
                }
            continue

        prior = state["sources"].get(sid) or {}
        prior_count = int(prior.get("last_good_count") or 0)
        if current_count != 0 or prior_count < 2:
            continue
        if row.get("status") in {"covered_elsewhere", "monitored_confirmed_zero"} or row.get("verified_inactive") is True:
            continue
        active_prior = [item for item in prior.get("events") or [] if (event_end_day(item) or date.min) >= today]
        if not active_prior:
            continue

        url = urls.get(norm(row.get("name")))
        if not url or not is_structured_web_url(url):
            continue
        checked += 1
        ok, http_status, _, error = fetch(url)
        if not ok or http_status != 200:
            suspected.append({
                "source_id": sid,
                "state": "drop_detected_but_source_unreachable",
                "last_good_count": prior_count,
                "active_prior_events": len(active_prior),
                "url": url,
                "http_status": http_status,
                "error": error,
            })
            continue

        source_restored = 0
        for item in active_prior:
            key = event_key(item)
            if key in known_keys:
                continue
            editorial = item.setdefault("editorial", {})
            editorial["preserved_by_parser_drift_guard"] = True
            editorial["parser_drift_preserved_at"] = now
            editorial["parser_drift_source_id"] = sid
            dataset.setdefault("events", []).append(item)
            known_keys.add(key)
            source_restored += 1
        suspected.append({
            "source_id": sid,
            "state": "suspected_parser_drift_preserved",
            "last_good_count": prior_count,
            "active_prior_events": len(active_prior),
            "restored_events": source_restored,
            "url": url,
            "http_status": 200,
        })
        if source_restored:
            restored.append({"source_id": sid, "events": source_restored})

    dataset["events"] = sorted(
        dataset.get("events") or [],
        key=lambda item: (str((item.get("schedule") or {}).get("start") or ""), str(item.get("title") or "")),
    )
    recalc_counts(dataset)
    state["generated_at"] = now
    report = {
        "schema_version": "1.0.0",
        "generated_at": now,
        "checked_suspected_sources": checked,
        "suspected_sources": suspected,
        "restored_sources": restored,
        "restored_events": sum(row["events"] for row in restored),
        "state_source_snapshots": len(state["sources"]),
    }
    return dataset, state, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Preserve still-current last-good events when a structured source unexpectedly drops to zero while its site remains reachable.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    dataset = load(DATASET_PATH)
    coverage = load(COVERAGE_PATH)
    catalog = load(CATALOG_PATH)
    state = load(STATE_PATH, {"schema_version": "1.0.0", "sources": {}})
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    updated, next_state, report = build(dataset, coverage, catalog, state, today)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.no_write:
        save(DATASET_PATH, updated)
        save(STATE_PATH, next_state)
        save(REPORT_PATH, report)


if __name__ == "__main__":
    main()
