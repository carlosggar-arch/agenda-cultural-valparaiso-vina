from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from event_page_tools import (
    best_matching_event,
    date_part,
    event_detail_url,
    event_status,
    extract_event_candidates,
    fetch,
    location_from_candidate,
    norm,
    offer_from_candidate,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
REPORT_PATH = ROOT / "app/data/quality/upcoming-revalidation.json"
TIMEZONE = "America/Santiago"
TEATRO_VINA_CARTELERA_URL = "https://teatrovina.cl/cartelera/"
TEATRO_VINA_HOSTS = {"teatrovina.cl", "www.teatrovina.cl"}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs) -> None:
        if tag.casefold() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag) -> None:
        if tag.casefold() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data) -> None:
        if not self._skip_depth:
            text = " ".join(str(data or "").split())
            if text:
                self.parts.append(text)


def _visible_text(markup: str) -> str:
    parser = _VisibleTextParser()
    try:
        parser.feed(markup or "")
    except Exception:
        return ""
    return " ".join(parser.parts)


def _is_teatro_vina(item: dict) -> bool:
    links = item.get("links") or {}
    for value in (links.get("official"), links.get("source"), item.get("source_url")):
        try:
            host = urlparse(str(value or "")).netloc.casefold()
        except ValueError:
            continue
        if host in TEATRO_VINA_HOSTS:
            return True
    return False


def teatro_vina_visible_time(markup: str, title: str, expected_day: str) -> str | None:
    """Return a unique visible Teatro Viña time for title+date.

    The Teatro's public cartelera is treated as the schedule authority when its
    visible date/title/time trio is unambiguous. This intentionally protects us
    from plugin JSON-LD metadata that can disagree with the time shown to users.
    """
    if not title or not expected_day:
        return None
    text = _visible_text(markup)
    if not text:
        return None
    title_key = norm(title)
    if not title_key:
        return None

    pattern = re.compile(
        r"\b(\d{1,2})[./-](\d{1,2})\s+(20\d{2})\s+([01]?\d|2[0-3]):([0-5]\d)\s*(?:hr|hrs|horas?)?\b",
        flags=re.I,
    )
    rows = list(pattern.finditer(text))
    matched_times: set[str] = set()
    for index, match in enumerate(rows):
        try:
            row_day = date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
        except ValueError:
            continue
        if row_day != expected_day:
            continue
        segment_end = rows[index + 1].start() if index + 1 < len(rows) else min(len(text), match.end() + 1200)
        segment = text[match.end():segment_end]
        if title_key in norm(segment):
            matched_times.add(f"{int(match.group(4)):02d}:{match.group(5)}")

    return next(iter(matched_times)) if len(matched_times) == 1 else None


def _teatro_vina_visible_start(item: dict, candidate: dict, cartelera_markup: str | None) -> str | None:
    if not cartelera_markup:
        return None
    expected_day = date_part(candidate.get("startDate")) or date_part((item.get("schedule") or {}).get("start"))
    visible_time = teatro_vina_visible_time(cartelera_markup, str(item.get("title") or ""), expected_day)
    if not visible_time:
        return None
    local = datetime.fromisoformat(f"{expected_day}T{visible_time}:00").replace(tzinfo=ZoneInfo(TIMEZONE))
    return local.isoformat(timespec="seconds")


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


def _parsed_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if "T" not in text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _pretty_day(value: str | None) -> str:
    raw = date_part(value)
    if not raw:
        return str(value or "")
    try:
        return date.fromisoformat(raw).strftime("%d-%m-%Y")
    except ValueError:
        return raw


def pretty_schedule(start: str, end: str | None) -> str:
    """Normalize public schedule text from canonical start/end fields."""
    start_day = date_part(start)
    end_day = date_part(end)
    start_dt = _parsed_datetime(start)
    end_dt = _parsed_datetime(end)

    if start_day and end_day == start_day:
        day = _pretty_day(start)
        if start_dt:
            start_time = start_dt.strftime("%H:%M")
            if end_dt:
                end_time = end_dt.strftime("%H:%M")
                if end_time != start_time:
                    return f"{day} · {start_time}–{end_time}"
            return f"{day} · {start_time}"
        return day

    def pretty(value: str | None) -> str:
        dt = _parsed_datetime(value)
        if dt:
            return f"{_pretty_day(value)} · {dt.strftime('%H:%M')}"
        return _pretty_day(value)

    if not end or end == start:
        return pretty(start)
    return f"{pretty(start)} – {pretty(end)}"


def apply_candidate(
    item: dict,
    candidate: dict,
    verified_at: str,
    *,
    start_confidence: str = "official_revalidation",
) -> list[str]:
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
        start_changed = new_start != old_start
        end_changed = bool(new_end and date_part(new_end) and new_end != old_end)
        if start_changed:
            schedule["start"] = new_start
            schedule["start_confidence"] = start_confidence
            changes.append("start")
        if end_changed:
            schedule["end"] = new_end
            schedule["end_confidence"] = "official_revalidation"
            changes.append("end")

        canonical_display = pretty_schedule(
            str(schedule.get("start") or new_start),
            str(schedule.get("end") or "") or None,
        )
        if canonical_display and canonical_display != str(schedule.get("display_text") or ""):
            schedule["display_text"] = canonical_display
            changes.append("display_text")

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


def _protect_teatro_vina_start(item: dict, candidate: dict, cartelera_markup: str | None) -> tuple[dict, str]:
    """Never let Teatro Viña plugin metadata silently replace a visible schedule."""
    candidate = copy.deepcopy(candidate)
    visible_start = _teatro_vina_visible_start(item, candidate, cartelera_markup)
    if visible_start:
        candidate["startDate"] = visible_start
        return candidate, "official_visible_schedule"

    candidate_day = date_part(candidate.get("startDate"))
    current_start = str((item.get("schedule") or {}).get("start") or "").strip()
    current_day = date_part(current_start)
    if candidate_day and candidate_day == current_day and current_start:
        candidate["startDate"] = current_start
    elif candidate_day:
        # A date change may still be useful, but an unconfirmed plugin time is not.
        candidate["startDate"] = candidate_day
    return candidate, "official_revalidation"


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

    cartelera_markup: str | None = None
    cartelera_state = "not_needed"
    if any(_is_teatro_vina(item) for item in targets):
        ok, status_code, markup, error = fetch(TEATRO_VINA_CARTELERA_URL)
        if ok:
            cartelera_markup = markup
            cartelera_state = "ok"
        else:
            cartelera_state = f"error:{status_code or ''}:{error or ''}"

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

        start_confidence = "official_revalidation"
        visible_schedule_used = False
        if _is_teatro_vina(item):
            candidate, start_confidence = _protect_teatro_vina_start(item, candidate, cartelera_markup)
            visible_schedule_used = start_confidence == "official_visible_schedule"

        fields = apply_candidate(item, candidate, verified_at, start_confidence=start_confidence)
        if fields:
            changed += 1
            state = "updated"
        else:
            state = "verified_unchanged"
        report_rows.append({
            "id": item.get("id"),
            "state": state,
            "url": url,
            "match_score": round(score, 3),
            "fields": fields,
            "visible_schedule_used": visible_schedule_used,
        })

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
        "teatro_vina_cartelera": cartelera_state,
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
