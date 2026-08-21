from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import refresh_official_source_recoveries_legacy as legacy

# Re-export the stable parsing/recovery API used by existing tests and callers.
parse = legacy.parse
detail_clock = legacy.detail_clock
rioja_venue = legacy.rioja_venue
visitavina_occurrences = legacy.visitavina_occurrences
make_rioja_event = legacy.make_rioja_event
parque_visible_multidates = legacy.parque_visible_multidates
parque_event_url = legacy.parque_event_url

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
PRIORITY_REPORT_PATH = ROOT / "app/data/quality/priority-zero-monitors.json"
TIMEZONE = legacy.TIMEZONE
TZ = legacy.TZ
MAX_HORIZON_DAYS = legacy.MAX_HORIZON_DAYS
PARQUE_REASON = legacy.PARQUE_REASON
SERIES_STATE_KEY = "series_state"


def canonical_url(value: str) -> str:
    parsed = urlparse(str(value or ""))
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _event_start(event: dict) -> str:
    return str((event.get("schedule") or {}).get("start") or "")


def _event_day(event: dict) -> str:
    return _event_start(event)[:10]


def _series_key(url: str, title: str = "") -> str:
    canonical = canonical_url(url)
    if canonical:
        return canonical
    normalized = legacy.norm(title)
    return f"title:{normalized}" if normalized else ""


def _load_previous_series_state() -> list[dict]:
    if not PRIORITY_REPORT_PATH.is_file():
        return []
    try:
        payload = json.loads(PRIORITY_REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    recovery = ((payload.get("official_source_recoveries") or {}).get("parque_cultural_multidate") or {})
    rows = recovery.get(SERIES_STATE_KEY) or []
    return [copy.deepcopy(row) for row in rows if isinstance(row, dict)]


def _template_event(event: dict) -> dict:
    template = copy.deepcopy(event)
    editorial = template.setdefault("editorial", {})
    if editorial.get("reason") == PARQUE_REASON:
        editorial.pop("reason", None)
    editorial.pop("multidate_series_key", None)
    editorial.pop("series_state", None)
    return template


def _merge_occurrence(entry: dict, event: dict) -> None:
    start = _event_start(event)
    if len(start) < 10:
        return
    day = start[:10]
    occurrences = entry.setdefault("occurrences", [])
    current = next((row for row in occurrences if str(row.get("start") or "")[:10] == day), None)
    if current is None:
        current = {"start": start}
        occurrences.append(current)
    if event.get("title"):
        current["title"] = str(event["title"])
    if event.get("description"):
        current["description"] = str(event["description"])
    occurrences.sort(key=lambda row: str(row.get("start") or ""))


def _state_from_event(event: dict) -> tuple[str, dict] | tuple[None, None]:
    url = parque_event_url(event)
    if not url:
        return None, None
    key = str((event.get("editorial") or {}).get("multidate_series_key") or _series_key(url, str(event.get("title") or "")))
    if not key:
        return None, None
    entry = {
        "series_key": key,
        "source_url": canonical_url(url),
        "title": str(event.get("title") or ""),
        "parent_id": str((event.get("editorial") or {}).get("multidate_parent_id") or event.get("id") or ""),
        "template_event": _template_event(event),
        "occurrences": [],
        "last_verified_at": str(event.get("last_verified_at") or ""),
    }
    _merge_occurrence(entry, event)
    return key, entry


def _merge_event_into_state(state_by_key: dict[str, dict], event: dict) -> None:
    key, fresh = _state_from_event(event)
    if not key or fresh is None:
        return
    entry = state_by_key.get(key)
    if entry is None:
        state_by_key[key] = fresh
        return
    if not isinstance(entry.get("template_event"), dict):
        entry["template_event"] = fresh["template_event"]
    entry.setdefault("source_url", fresh["source_url"])
    entry.setdefault("title", fresh["title"])
    entry.setdefault("parent_id", fresh["parent_id"])
    _merge_occurrence(entry, event)


def _series_entry_from_official_page(event: dict, url: str, starts: list[str], previous: dict | None) -> dict:
    previous = copy.deepcopy(previous or {})
    old_by_day = {
        str(row.get("start") or "")[:10]: row
        for row in previous.get("occurrences") or []
        if isinstance(row, dict) and str(row.get("start") or "")[:10]
    }
    occurrences = []
    for start in sorted(dict.fromkeys(starts)):
        row = {"start": start}
        old = old_by_day.get(start[:10]) or {}
        # Keep any date-specific title/description already curated.
        for field in ("title", "description"):
            if old.get(field):
                row[field] = old[field]
        occurrences.append(row)
    return {
        "series_key": _series_key(url, str(event.get("title") or "")),
        "source_url": canonical_url(url),
        "title": str(event.get("title") or ""),
        "parent_id": str(event.get("id") or previous.get("parent_id") or ""),
        "template_event": _template_event(event),
        "occurrences": occurrences,
        "last_verified_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }


def _same_series_occurrence(event: dict, entry: dict, start: str) -> bool:
    if _event_day(event) != start[:10]:
        return False
    event_url = parque_event_url(event)
    state_url = canonical_url(str(entry.get("source_url") or ""))
    if event_url and state_url and canonical_url(event_url) == state_url:
        return True
    title = legacy.norm(entry.get("title"))
    return bool(title and legacy.norm(event.get("title")) == title)


def _materialize(entry: dict, occurrence: dict) -> dict | None:
    template = entry.get("template_event")
    start = str(occurrence.get("start") or "")
    if not isinstance(template, dict) or len(start) < 16:
        return None
    event = legacy.clone_parque_event(template, start)
    if occurrence.get("title"):
        event["title"] = occurrence["title"]
    if occurrence.get("description"):
        event["description"] = occurrence["description"]
    editorial = event.setdefault("editorial", {})
    editorial["reason"] = PARQUE_REASON
    editorial["multidate_series_key"] = entry.get("series_key")
    editorial["series_state"] = "persistent_official_schedule"
    event["source_id"] = event.get("source_id") or "pcdv"
    return event


def recover_parque_multidate(dataset: dict, today: date) -> dict:
    events = list(dataset.get("events") or [])
    generated_before = [
        event for event in events
        if str((event.get("editorial") or {}).get("reason") or "") == PARQUE_REASON
    ]
    base = [
        event for event in events
        if str((event.get("editorial") or {}).get("reason") or "") != PARQUE_REASON
    ]

    state_by_key: dict[str, dict] = {}
    for row in _load_previous_series_state():
        key = str(row.get("series_key") or _series_key(str(row.get("source_url") or ""), str(row.get("title") or "")))
        if key:
            row["series_key"] = key
            state_by_key[key] = row

    # Generated children are also evidence. This makes the mechanism resilient
    # even if a quality-report commit is temporarily delayed.
    for event in generated_before:
        _merge_event_into_state(state_by_key, event)

    horizon = today + timedelta(days=MAX_HORIZON_DAYS)
    pages_checked = 0
    multidate_pages = 0
    fetch_errors = 0
    series_refreshed = 0

    # Revalidate both currently visible parent events and persisted series.
    candidates = list(base)
    for entry in state_by_key.values():
        template = entry.get("template_event")
        if isinstance(template, dict):
            candidates.append(template)

    seen_urls: set[str] = set()
    for event in candidates:
        url = parque_event_url(event)
        if not url:
            continue
        url = canonical_url(url)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        reference_start = _event_start(event)
        reference_day = reference_start[:10]
        try:
            reference_date = date.fromisoformat(reference_day)
        except ValueError:
            continue
        if reference_date > horizon or reference_date < today - timedelta(days=14):
            continue

        ok, _status, markup, _error = legacy.fetch(url)
        if not ok:
            fetch_errors += 1
            continue
        pages_checked += 1
        starts = parque_visible_multidates(markup, reference_start)
        if len(starts) <= 1:
            continue
        multidate_pages += 1
        key = _series_key(url, str(event.get("title") or ""))
        state_by_key[key] = _series_entry_from_official_page(event, url, starts, state_by_key.get(key))
        series_refreshed += 1

    active_state: list[dict] = []
    generated: list[dict] = []
    for key, entry in sorted(state_by_key.items()):
        rows = [
            row for row in (entry.get("occurrences") or [])
            if isinstance(row, dict) and str(row.get("start") or "")[:10]
        ]
        today_or_future = [
            row for row in rows
            if today.isoformat() <= str(row.get("start") or "")[:10] <= horizon.isoformat()
        ]
        if not today_or_future:
            continue

        stable_entry = copy.deepcopy(entry)
        stable_entry["series_key"] = key
        stable_entry["occurrences"] = sorted(rows, key=lambda row: str(row.get("start") or ""))
        active_state.append(stable_entry)

        for occurrence in today_or_future:
            start = str(occurrence.get("start") or "")
            if any(_same_series_occurrence(existing, stable_entry, start) for existing in base + generated):
                continue
            child = _materialize(stable_entry, occurrence)
            if child:
                generated.append(child)

    dataset["events"] = base + generated
    return {
        "state": "persistent_multidate_series_active" if active_state else "no_active_multidate_series",
        "pages_checked": pages_checked,
        "multidate_pages": multidate_pages,
        "events_added": len(generated),
        "fetch_errors": fetch_errors,
        "series_refreshed": series_refreshed,
        "series_active": len(active_state),
        SERIES_STATE_KEY: active_state,
    }


def run(no_write: bool = False) -> dict:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    today = datetime.now(TZ).date()
    parque = recover_parque_multidate(dataset, today)
    rioja = legacy.recover_rioja(dataset, today)
    legacy.refresh_counts(dataset)
    if not no_write:
        DATASET_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "parque_cultural_multidate": parque,
        "palacio_rioja": rioja,
        "events_after": len(dataset.get("events") or []),
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
