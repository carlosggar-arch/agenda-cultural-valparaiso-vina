from __future__ import annotations

import argparse
import copy
import html
import json
import re
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from revalidate_upcoming_events import pretty_schedule

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
REPORT_PATH = ROOT / "app/data/quality/schedule-authority.json"
TIMEZONE = "America/Santiago"
SALAS_SCD_HOSTS = {"salasscd.cl", "www.salasscd.cl"}
VALPO_CULTURA_HOSTS = {"valpocultura.cl", "www.valpocultura.cl"}
CULTURA_USM_HOSTS = {"cultura.usm.cl", "www.cultura.usm.cl"}


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs) -> None:
        if tag.casefold() in {"script", "style", "noscript"}:
            self.skip += 1
        elif not self.skip and tag.casefold() in {"br", "p", "div", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag) -> None:
        if tag.casefold() in {"script", "style", "noscript"}:
            if self.skip:
                self.skip -= 1
        elif not self.skip and tag.casefold() in {"p", "div", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data) -> None:
        if not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        value = html.unescape("".join(self.parts)).replace("\xa0", " ")
        return re.sub(r"[ \t]+", " ", value)


def visible_text(markup: str) -> str:
    parser = VisibleTextParser()
    try:
        parser.feed(markup or "")
    except Exception:
        return ""
    return parser.text()


def fetch(url: str) -> tuple[bool, int | None, str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=25) as response:  # nosec B310 - event-specific HTTPS source
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return True, getattr(response, "status", 200), text, None
    except HTTPError as exc:
        return False, exc.code, "", f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, None, "", f"{type(exc).__name__}: {exc}"


def event_url(item: dict) -> str | None:
    links = item.get("links") or {}
    for value in (links.get("official"), links.get("source"), item.get("source_url")):
        url = str(value or "").strip()
        if not url:
            continue
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        if parsed.scheme == "https" and parsed.path and parsed.path != "/":
            return url
    return None


def host_for(item: dict) -> str:
    url = event_url(item)
    if not url:
        return ""
    try:
        return urlparse(url).netloc.casefold()
    except ValueError:
        return ""


def _twelve_hour(hour: str, minute: str | None, meridiem: str) -> tuple[int, int]:
    value = int(hour)
    if not 1 <= value <= 12:
        raise ValueError("invalid 12-hour clock")
    marker = meridiem.casefold()
    value %= 12
    if marker == "pm":
        value += 12
    return value, int(minute or "00")


def salas_scd_formal_range(markup: str) -> tuple[str, str] | None:
    """Read only Salas SCD's formal `Hora start - end` block.

    This deliberately ignores prose such as `Hora de Apertura de Puertas`,
    `Hora aprox. de inicio` and `Hora aprox. de término`, so auxiliary clocks
    can never be concatenated into fake sessions.
    """
    text = visible_text(markup)
    pattern = re.compile(
        r"(?:^|\n)\s*Hora\s*\n?\s*"
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*[-–—]\s*"
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        flags=re.I,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        return None
    match = matches[0]
    try:
        start_h, start_m = _twelve_hour(match.group(1), match.group(2), match.group(3))
        end_h, end_m = _twelve_hour(match.group(4), match.group(5), match.group(6))
    except ValueError:
        return None
    return f"{start_h:02d}:{start_m:02d}", f"{end_h:02d}:{end_m:02d}"


def cultura_usm_formal_range(markup: str) -> tuple[str, str] | None:
    """Read Cultura USM's labeled start/end pair as one event range.

    Cultura USM exposes `Hora inicio` and `Hora término` as two fields of the
    same event. They must never be promoted to two separate performances.
    """
    text = visible_text(markup)
    start_pattern = re.compile(
        r"(?:^|\n)\s*Hora\s+(?:de\s+)?inicio\s*:?\s*(?:\n\s*)?(\d{1,2}):(\d{2})\b",
        flags=re.I,
    )
    end_pattern = re.compile(
        r"(?:^|\n)\s*Hora\s+(?:de\s+)?(?:t[eé]rmino|fin)\s*:?\s*(?:\n\s*)?(\d{1,2}):(\d{2})\b",
        flags=re.I,
    )
    starts = start_pattern.findall(text)
    ends = end_pattern.findall(text)
    if len(starts) != 1 or len(ends) != 1:
        return None
    start_h, start_m = (int(starts[0][0]), int(starts[0][1]))
    end_h, end_m = (int(ends[0][0]), int(ends[0][1]))
    if not (0 <= start_h <= 23 and 0 <= end_h <= 23 and 0 <= start_m <= 59 and 0 <= end_m <= 59):
        return None
    return f"{start_h:02d}:{start_m:02d}", f"{end_h:02d}:{end_m:02d}"


def _jsonld_objects(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _jsonld_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _jsonld_objects(nested)


def valpocultura_structured_times(markup: str) -> tuple[str, str | None] | None:
    """Preserve explicit JSON-LD times; never manufacture midnight from dates."""
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        markup or "",
        flags=re.I | re.S,
    ):
        try:
            payload = json.loads(html.unescape(match.group(1)).strip())
        except json.JSONDecodeError:
            continue
        for obj in _jsonld_objects(payload):
            types = obj.get("@type")
            types = types if isinstance(types, list) else [types]
            if "Event" not in types:
                continue
            start = str(obj.get("startDate") or "").strip()
            if "T" not in start:
                continue
            try:
                datetime.fromisoformat(start.replace("Z", "+00:00"))
            except ValueError:
                continue
            end = str(obj.get("endDate") or "").strip()
            if "T" in end:
                try:
                    datetime.fromisoformat(end.replace("Z", "+00:00"))
                except ValueError:
                    end = ""
            else:
                end = ""
            return start, end or None
    return None


def _day(value: object) -> str | None:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text[:10]).isoformat() if text else None
    except ValueError:
        return None


def _local_iso(day: str, clock: str) -> str:
    dt = datetime.fromisoformat(f"{day}T{clock}:00").replace(tzinfo=ZoneInfo(TIMEZONE))
    return dt.isoformat(timespec="seconds")


def apply_authority(item: dict, markup: str) -> list[str]:
    schedule = item.setdefault("schedule", {})
    current_day = _day(schedule.get("start"))
    if not current_day:
        return []

    host = host_for(item)
    new_start: str | None = None
    new_end: str | None = None
    authority: str | None = None

    if host in SALAS_SCD_HOSTS:
        clock_range = salas_scd_formal_range(markup)
        if not clock_range:
            return []
        new_start = _local_iso(current_day, clock_range[0])
        new_end = _local_iso(current_day, clock_range[1])
        authority = "official_visible_schedule"
    elif host in CULTURA_USM_HOSTS:
        clock_range = cultura_usm_formal_range(markup)
        if not clock_range:
            return []
        new_start = _local_iso(current_day, clock_range[0])
        new_end = _local_iso(current_day, clock_range[1])
        authority = "official_visible_schedule"
    elif host in VALPO_CULTURA_HOSTS and str(item.get("source_id") or "") == "valpocultura":
        structured = valpocultura_structured_times(markup)
        if not structured:
            return []
        if _day(structured[0]) != current_day:
            return []
        new_start, structured_end = structured
        new_end = structured_end
        authority = "official_structured_schedule"
    else:
        return []

    changes: list[str] = []
    if new_start and new_start != str(schedule.get("start") or ""):
        schedule["start"] = new_start
        changes.append("start")
    if new_end and new_end != str(schedule.get("end") or ""):
        schedule["end"] = new_end
        changes.append("end")

    if authority and (changes or schedule.get("start_confidence") != authority):
        schedule["start_confidence"] = authority
        if "start_confidence" not in changes:
            changes.append("start_confidence")
    if new_end and schedule.get("end_confidence") != authority:
        schedule["end_confidence"] = authority
        changes.append("end_confidence")

    display = pretty_schedule(str(schedule.get("start") or ""), str(schedule.get("end") or "") or None)
    if display and display != str(schedule.get("display_text") or ""):
        schedule["display_text"] = display
        changes.append("display_text")
    return sorted(set(changes))


def is_target(item: dict, today: date, days: int) -> bool:
    if item.get("event_type") != "event":
        return False
    host = host_for(item)
    if host not in SALAS_SCD_HOSTS | VALPO_CULTURA_HOSTS | CULTURA_USM_HOSTS:
        return False
    if host in VALPO_CULTURA_HOSTS and str(item.get("source_id") or "") != "valpocultura":
        return False
    start_day = _day((item.get("schedule") or {}).get("start"))
    if not start_day:
        return False
    value = date.fromisoformat(start_day)
    return today <= value <= today + timedelta(days=max(1, days))


def build(dataset: dict, today: date, *, days: int = 120, max_fetch: int = 30) -> tuple[dict, dict]:
    output = copy.deepcopy(dataset)
    rows: list[dict] = []
    fetched = updated = errors = skipped = 0
    for item in output.get("events") or []:
        if not isinstance(item, dict) or not is_target(item, today, days):
            continue
        url = event_url(item)
        if not url:
            skipped += 1
            continue
        if fetched >= max_fetch:
            skipped += 1
            rows.append({"id": item.get("id"), "state": "fetch_budget_exhausted", "url": url})
            continue
        fetched += 1
        ok, status, markup, error = fetch(url)
        if not ok:
            errors += 1
            rows.append({"id": item.get("id"), "state": "fetch_error", "url": url, "http_status": status, "error": error})
            continue
        fields = apply_authority(item, markup)
        if fields:
            updated += 1
            editorial = item.setdefault("editorial", {})
            editorial["schedule_authority_fields"] = fields
            editorial["schedule_authority_url"] = url
            rows.append({"id": item.get("id"), "state": "updated", "url": url, "fields": fields})
        else:
            rows.append({"id": item.get("id"), "state": "verified_unchanged", "url": url, "fields": []})

    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds"),
        "window_days": days,
        "fetched": fetched,
        "updated_events": updated,
        "fetch_errors": errors,
        "skipped": skipped,
        "rows": rows,
    }
    return output, report


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply source-specific schedule authority rules to Valpo events.")
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--max-fetch", type=int, default=30)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    dataset = load(DATASET_PATH)
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    updated, report = build(dataset, today, days=max(1, args.days), max_fetch=max(1, args.max_fetch))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.no_write:
        save(DATASET_PATH, updated)
        save(REPORT_PATH, report)


if __name__ == "__main__":
    main()
