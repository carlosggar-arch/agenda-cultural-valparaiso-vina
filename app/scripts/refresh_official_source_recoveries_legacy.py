from __future__ import annotations

import copy
import hashlib
import html
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
TIMEZONE = "America/Santiago"
TZ = ZoneInfo(TIMEZONE)
VISITAVINA_LISTING_URL = "https://visitavina.munivina.cl/actividades/"
VISITAVINA_HOSTS = {"visitavina.munivina.cl", "www.visitavina.munivina.cl"}
RIOJA_SOURCE_ID = "visitavina_palacio_rioja_recovery"
RIOJA_SOURCE_NAME = "Visita Viña — Museo Palacio Rioja"
RIOJA_COVERED_SOURCE_ID = "museo_palacio_rioja"
RIOJA_VENUE_ALIASES = {
    "palacio rioja",
    "museo palacio rioja",
    "jardines palacio rioja",
    "sala aldo francia",
    "palacio rioja sala aldo francia",
}
PARQUE_HOSTS = {"parquecultural.cl", "www.parquecultural.cl"}
PARQUE_REASON = "official_multidate:parquecultural"
MAX_HORIZON_DAYS = 60
MAX_VISITAVINA_DETAILS = 180
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
TIME_RANGE = re.compile(r"(?<!\d)(\d{1,2}):([0-5]\d)\s*(am|pm)\s*[-–]\s*(\d{1,2}):([0-5]\d)\s*(am|pm)", re.I)
TIME_SINGLE = re.compile(r"(?<!\d)(\d{1,2}):([0-5]\d)\s*(am|pm)\b", re.I)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def fetch(url: str, timeout: int = 12) -> tuple[bool, int | None, str, str | None]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - official HTTPS sources
            raw = response.read(); charset = response.headers.get_content_charset() or "utf-8"
            try: markup = raw.decode(charset, errors="replace")
            except LookupError: markup = raw.decode("utf-8", errors="replace")
            return True, getattr(response, "status", 200), markup, None
    except HTTPError as exc:
        return False, exc.code, "", f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, None, "", f"{type(exc).__name__}: {exc}"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hrefs: list[str] = []
        self.meta: dict[str, str] = {}
        self.h1_parts: list[str] = []
        self._skip = 0
        self._in_h1 = False

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self._skip += 1; return
        if self._skip: return
        if tag == "a" and values.get("href"):
            self.hrefs.append(str(values["href"]).strip())
        if tag == "meta":
            key = str(values.get("property") or values.get("name") or "").strip().casefold()
            value = str(values.get("content") or "").strip()
            if key and value: self.meta[key] = value
        if tag == "h1": self._in_h1 = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            if self._skip: self._skip -= 1
            return
        if tag == "h1": self._in_h1 = False

    def handle_data(self, data: str) -> None:
        if self._skip: return
        text = re.sub(r"\s+", " ", html.unescape(str(data or "")).replace("\xa0", " ")).strip()
        if not text: return
        self.parts.append(text)
        if self._in_h1: self.h1_parts.append(text)

    @property
    def h1(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.h1_parts)).strip()

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def parse(markup: str) -> PageParser:
    parser = PageParser(); parser.feed(markup or ""); return parser


def canonical_url(value: str) -> str:
    parsed = urlparse(value)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _to_24h(hour: int, minute: str, meridiem: str) -> str:
    token = meridiem.casefold()
    if token == "pm" and hour != 12: hour += 12
    if token == "am" and hour == 12: hour = 0
    return f"{hour:02d}:{minute}"


def detail_clock(parser: PageParser) -> tuple[str | None, str | None]:
    for index, part in enumerate(parser.parts[:45]):
        if norm(part) != "hora": continue
        nearby = " ".join(parser.parts[index + 1:index + 4])
        match = TIME_RANGE.search(nearby)
        if match:
            return _to_24h(int(match.group(1)), match.group(2), match.group(3)), _to_24h(int(match.group(4)), match.group(5), match.group(6))
        match = TIME_SINGLE.search(nearby)
        if match:
            return _to_24h(int(match.group(1)), match.group(2), match.group(3)), None
    for part in parser.parts[:30]:
        match = TIME_RANGE.search(part)
        if match:
            return _to_24h(int(match.group(1)), match.group(2), match.group(3)), _to_24h(int(match.group(4)), match.group(5), match.group(6))
    return None, None


def rioja_venue(parser: PageParser) -> str | None:
    for index, part in enumerate(parser.parts[:55]):
        if norm(part) == "lugar":
            for candidate in parser.parts[index + 1:index + 5]:
                key = norm(candidate)
                if key in RIOJA_VENUE_ALIASES:
                    return candidate.strip().rstrip(",")
        key = norm(part)
        if key in RIOJA_VENUE_ALIASES:
            return part.strip().rstrip(",")
    return None


def visitavina_occurrences(markup: str, today: date, horizon: date) -> list[tuple[date, str]]:
    parser = parse(markup); found: dict[tuple[date, str], str] = {}
    for href in parser.hrefs:
        absolute = urljoin(VISITAVINA_LISTING_URL, href)
        parsed = urlparse(absolute)
        if parsed.netloc.casefold() not in VISITAVINA_HOSTS or not parsed.path.startswith("/actividad/"):
            continue
        for raw in parse_qs(parsed.query).get("occurrence", []):
            try: day = date.fromisoformat(raw[:10])
            except ValueError: continue
            if today <= day <= horizon:
                found[(day, canonical_url(absolute))] = absolute
    return [(day, url) for (day, _), url in sorted(found.items(), key=lambda item: (item[0][0], item[0][1]))]


def category_for_title(title: str) -> tuple[str, str]:
    key = norm(title)
    if any(token in key for token in ("exposicion", "exhibicion", "muestra temporal")):
        return "exposiciones", "Exposiciones"
    if "taller" in key:
        return "cursos-talleres", "Cursos y talleres"
    if any(token in key for token in ("cine", "cinematograf")):
        return "cine", "Cine"
    if any(token in key for token in ("concierto", "musica", "jazz")):
        return "musica", "Música"
    return "cultura", "Cultura"


def _iso(day: date, clock: str | None) -> str:
    if not clock: return day.isoformat()
    return datetime.fromisoformat(f"{day.isoformat()}T{clock}:00").replace(tzinfo=TZ).isoformat(timespec="seconds")


def make_rioja_event(day: date, occurrence_url: str, parser: PageParser, venue: str) -> dict:
    title = parser.h1.strip() or "Actividad en Palacio Rioja"
    if norm(title).startswith("copia de "):
        title = re.sub(r"^\s*Copia\s+de\s+", "", title, flags=re.I)
    start_clock, end_clock = detail_clock(parser)
    start = _iso(day, start_clock); end = _iso(day, end_clock) if end_clock else None
    cat_id, cat_label = category_for_title(title)
    verified = datetime.now(TZ).isoformat(timespec="seconds")
    text_key = norm(parser.text)
    free = any(token in text_key for token in ("actividad gratuita", "entrada liberada", "entrada gratuita"))
    digest = hashlib.sha1(f"{RIOJA_SOURCE_ID}|{day.isoformat()}|{canonical_url(occurrence_url)}".encode()).hexdigest()[:18]
    return {
        "id": f"agenda_visitavina_rioja_{digest}", "title": title, "event_type": "event",
        "primary_category": {"id": cat_id, "label": cat_label}, "categories": [{"id": cat_id, "label": cat_label}],
        "schedule": {"mode": "dated", "start": start, "end": end, "timezone": TIMEZONE,
                     "display_text": f"{day.isoformat()}{' · ' + start_clock if start_clock else ''}{'–' + end_clock if end_clock else ''}",
                     "occurrences": [], "start_confidence": "official_visible_schedule", "end_confidence": "official_visible_schedule" if end else None},
        "location": {"venue_id": RIOJA_COVERED_SOURCE_ID, "city": "Viña del Mar", "commune": "Viña del Mar", "venue": venue,
                     "address": "Quillota 214, Viña del Mar", "online": False, "latitude": None, "longitude": None},
        "price": {"is_free": True if free else None, "currency": "CLP", "min_amount": 0 if free else None,
                  "max_amount": 0 if free else None, "display_text": "Gratis" if free else "Consultar condiciones"},
        "links": {"official": occurrence_url, "tickets": None, "registration": None, "source": VISITAVINA_LISTING_URL},
        "organizer": "Museo Palacio Rioja", "source_id": RIOJA_SOURCE_ID, "source_name": RIOJA_SOURCE_NAME,
        "source_url": VISITAVINA_LISTING_URL, "last_verified_at": verified,
        "public_status": {"source_official": True, "last_verified_at": verified, "registration_open": None,
                          "registration_closed": None, "cancelled": False, "sold_out": None, "price_stage": None,
                          "price_confirmed": free, "information_completeness": "complete" if start_clock else "partial",
                          "advisory_text": "Actividad recuperada desde la cartelera oficial municipal Visita Viña que enlaza la programación del Museo Palacio Rioja."},
        "description": "Actividad del Museo Palacio Rioja recuperada desde la cartelera oficial municipal de Viña del Mar.",
        "tags": [cat_label, "Museo Palacio Rioja", "Visita Viña"], "audience": None, "registration_requirements": None,
        "image": {"url": parser.meta.get("og:image"), "alt": title if parser.meta.get("og:image") else None},
        "editorial": {"classification": "event", "reason": "official_cross_source:visitavina_palacio_rioja",
                      "covered_source_ids": [RIOJA_COVERED_SOURCE_ID], "duration_days": 0},
    }


def semantic_key(item: dict) -> tuple[str, str, str]:
    return (norm(item.get("title")), str((item.get("schedule") or {}).get("start") or "")[:10], norm((item.get("location") or {}).get("venue")))


def _same_event(a: dict, b: dict) -> bool:
    if str((a.get("schedule") or {}).get("start") or "")[:10] != str((b.get("schedule") or {}).get("start") or "")[:10]: return False
    ta, tb = set(norm(a.get("title")).split()), set(norm(b.get("title")).split())
    if not ta or not tb: return False
    overlap = len(ta & tb) / max(1, min(len(ta), len(tb)))
    return overlap >= 0.72


def preserve_previous_event_image(event: dict, previous: list[dict]) -> dict:
    """Keep a previously verified event image when a source refresh omits it."""
    current_url = str((event.get("image") or {}).get("url") or "").strip()
    if current_url:
        return event
    match = next((item for item in previous if _same_event(item, event)), None)
    previous_url = str(((match or {}).get("image") or {}).get("url") or "").strip()
    if not previous_url:
        return event
    recovered = copy.deepcopy(event)
    recovered["image"] = copy.deepcopy(match["image"])
    recovered.setdefault("editorial", {})["image_preservation"] = "previous_verified_same_event"
    return recovered


def recover_rioja(dataset: dict, today: date) -> dict:
    events = list(dataset.get("events") or [])
    previous = [e for e in events if e.get("source_id") == RIOJA_SOURCE_ID and str((e.get("schedule") or {}).get("start") or "")[:10] >= today.isoformat()]
    base = [e for e in events if e.get("source_id") != RIOJA_SOURCE_ID]
    ok, status, markup, error = fetch(VISITAVINA_LISTING_URL)
    if not ok:
        dataset["events"] = base + previous
        return {"state": "listing_fetch_error_previous_preserved" if previous else "listing_fetch_error", "fetch_ok": False,
                "http_status": status, "error": error, "events_published": len(previous), "candidates": 0}

    occurrence_rows = visitavina_occurrences(markup, today, today + timedelta(days=MAX_HORIZON_DAYS))[:MAX_VISITAVINA_DETAILS]
    detail_rows: list[tuple[date, str, bool, int | None, str, str | None]] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch, url): (day, url) for day, url in occurrence_rows}
        for future in as_completed(futures):
            day, url = futures[future]
            try: detail_ok, detail_status, detail_markup, detail_error = future.result()
            except Exception as exc: detail_ok, detail_status, detail_markup, detail_error = False, None, "", str(exc)
            detail_rows.append((day, url, detail_ok, detail_status, detail_markup, detail_error))

    fresh: list[dict] = []
    checked = 0
    for day, url, detail_ok, _detail_status, detail_markup, _detail_error in sorted(detail_rows, key=lambda row: (row[0], row[1])):
        if not detail_ok: continue
        checked += 1; parser = parse(detail_markup); venue = rioja_venue(parser)
        if not venue: continue
        event = make_rioja_event(day, url, parser, venue)
        event = preserve_previous_event_image(event, previous)
        title_key = norm(event["title"])
        if any(token in title_key for token in ("exposicion temporal", "exhibicion temporal", "muestra temporal")):
            if any(norm(existing.get("title")) == title_key for existing in base):
                continue
        if any(_same_event(existing, event) for existing in base + fresh):
            continue
        fresh.append(event)

    dataset["events"] = base + fresh
    return {"state": "publishing_rioja_events" if fresh else "no_new_rioja_events", "fetch_ok": True, "http_status": status,
            "error": None, "candidates": len(occurrence_rows), "details_checked": checked, "events_published": len(fresh),
            "covered_source_id": RIOJA_COVERED_SOURCE_ID}


def parque_event_url(item: dict) -> str | None:
    links = item.get("links") or {}
    for value in (links.get("official"), item.get("source_url"), links.get("source")):
        try: parsed = urlparse(str(value or ""))
        except ValueError: continue
        if parsed.netloc.casefold() in PARQUE_HOSTS and parsed.path.startswith("/events/"):
            return canonical_url(str(value))
    return None


def parque_visible_multidates(markup: str, reference_start: str) -> list[str]:
    parser = parse(markup)
    text = unicodedata.normalize("NFKD", parser.text).encode("ascii", "ignore").decode("ascii").casefold()
    reference_day = str(reference_start or "")[:10]
    try: reference = date.fromisoformat(reference_day)
    except ValueError: return []
    month_pattern = "|".join(MONTHS)
    patterns = [
        re.compile(rf"funciones?.{{0,220}}?dias?\s+(.{{0,170}}?)\s+de\s+({month_pattern})(?:\s+de\s+(20\d{{2}}))?.{{0,120}}?(\d{{1,2}}):([0-5]\d)", re.I),
        re.compile(rf"presentaciones?.{{0,220}}?dias?\s+(.{{0,170}}?)\s+de\s+({month_pattern})(?:\s+de\s+(20\d{{2}}))?.{{0,120}}?(\d{{1,2}}):([0-5]\d)", re.I),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if not match: continue
        day_chunk, month_name, raw_year, hour, minute = match.groups()
        days = [int(value) for value in re.findall(r"\b([0-3]?\d)\b", day_chunk) if 1 <= int(value) <= 31]
        year = int(raw_year) if raw_year else reference.year; month = MONTHS[month_name]
        starts = []
        for day_number in dict.fromkeys(days):
            try: day = date(year, month, day_number)
            except ValueError: continue
            starts.append(datetime.fromisoformat(f"{day.isoformat()}T{int(hour):02d}:{minute}:00").replace(tzinfo=TZ).isoformat(timespec="seconds"))
        if len(starts) > 1 and reference_day in {value[:10] for value in starts}: return sorted(starts)
    return []


def clone_parque_event(base_event: dict, start: str) -> dict:
    clone = copy.deepcopy(base_event); day = start[:10]
    digest = hashlib.sha1(f"{base_event.get('id')}|{day}".encode()).hexdigest()[:18]
    clone["id"] = f"agenda_parquecultural_multidate_{digest}"
    schedule = clone.setdefault("schedule", {}); old_start = str(schedule.get("start") or ""); old_end = str(schedule.get("end") or "")
    schedule.update({"mode": "dated", "start": start, "timezone": TIMEZONE, "occurrences": [],
                     "start_confidence": "official_visible_multidate"})
    end = None
    try:
        old_start_dt = datetime.fromisoformat(old_start); old_end_dt = datetime.fromisoformat(old_end)
        duration = old_end_dt - old_start_dt
        if timedelta(0) < duration <= timedelta(hours=8): end = (datetime.fromisoformat(start) + duration).isoformat(timespec="seconds")
    except ValueError: pass
    schedule["end"] = end
    schedule["end_confidence"] = "derived_from_first_official_occurrence" if end else None
    schedule["display_text"] = f"{day} · {start[11:16]}" + (f"–{end[11:16]}" if end else "")
    editorial = clone.setdefault("editorial", {}); editorial["reason"] = PARQUE_REASON; editorial["multidate_parent_id"] = base_event.get("id")
    clone["last_verified_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    clone.setdefault("public_status", {})["last_verified_at"] = clone["last_verified_at"]
    return clone


def recover_parque_multidate(dataset: dict, today: date) -> dict:
    events = list(dataset.get("events") or [])
    base = [e for e in events if str((e.get("editorial") or {}).get("reason") or "") != PARQUE_REASON]
    generated: list[dict] = []; pages_checked = 0; multidate_pages = 0; errors = 0
    known = {(norm(e.get("title")), str((e.get("schedule") or {}).get("start") or "")[:10]) for e in base}
    horizon = today + timedelta(days=MAX_HORIZON_DAYS)
    for item in base:
        url = parque_event_url(item)
        if not url: continue
        start_day = str((item.get("schedule") or {}).get("start") or "")[:10]
        try: start_date = date.fromisoformat(start_day)
        except ValueError: continue
        if start_date > horizon or start_date < today - timedelta(days=10): continue
        ok, _status, markup, _error = fetch(url)
        if not ok: errors += 1; continue
        pages_checked += 1
        starts = parque_visible_multidates(markup, str((item.get("schedule") or {}).get("start") or ""))
        if len(starts) <= 1: continue
        multidate_pages += 1
        for start in starts:
            day = start[:10]
            if day == start_day or day < today.isoformat(): continue
            key = (norm(item.get("title")), day)
            if key in known: continue
            clone = clone_parque_event(item, start); generated.append(clone); known.add(key)
    dataset["events"] = base + generated
    return {"state": "multidate_events_expanded" if generated else "no_missing_multidate_occurrences", "pages_checked": pages_checked,
            "multidate_pages": multidate_pages, "events_added": len(generated), "fetch_errors": errors}


def refresh_counts(dataset: dict) -> None:
    events = dataset.get("events") or []
    dataset["events"] = sorted(events, key=lambda item: (str((item.get("schedule") or {}).get("start") or ""), str(item.get("title") or "")))
    dataset["counts"] = {
        "total": len(events), "events": sum(item.get("event_type") == "event" for item in events),
        "courses": sum(item.get("event_type") == "course" for item in events),
        "flexible_offers": sum(item.get("event_type") == "flexible_offer" for item in events),
        "programs": sum(item.get("event_type") == "program" for item in events),
    }


def run(no_write: bool = False) -> dict:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8")); today = datetime.now(TZ).date()
    parque = recover_parque_multidate(dataset, today); rioja = recover_rioja(dataset, today); refresh_counts(dataset)
    if not no_write:
        DATASET_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"parque_cultural_multidate": parque, "palacio_rioja": rioja, "events_after": len(dataset.get("events") or [])}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
