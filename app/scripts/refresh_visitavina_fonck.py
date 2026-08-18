from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
REPORT_PATH = ROOT / "app/data/quality/visitavina-fonck.json"
SOURCE_ID = "visitavina_fonck_recovery"
SOURCE_NAME = "Visita Viña — Museo Fonck"
COVERED_SOURCE_ID = "museo_fonck"
EVENT_URL = "https://visitavina.munivina.cl/actividad/taller-de-lengua-rapanui-2/"
TIMEZONE = "America/Santiago"
CITY = "Viña del Mar"
VENUE = "Museo Fonck"
ADDRESS = "4 Norte 784, Viña del Mar"
EXPECTED_TITLE = "taller de lengua rapanui"
MAX_HORIZON_DAYS = 90
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MONTH_PATTERN = "|".join(MONTHS)
DATE_LIST_SEGMENT = re.compile(
    rf"((?:\d{{1,2}}(?:\s*(?:,|y)\s*)?)+)\s+de\s+({MONTH_PATTERN})(?:\s+de\s+(20\d{{2}}))?",
    re.I,
)
OCCURRENCE_QUERY = re.compile(r"[?&]occurrence=(20\d{2}-\d{2}-\d{2})(?:[&#\"']|$)", re.I)
TIME_24 = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:.]([0-5]\d)\s*(?:h(?:oras?)?)?", re.I)
BLOCK_TAGS = {"br", "p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td"}


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.buffer: list[str] = []
        self.hrefs: list[str] = []
        self.skip = 0
        self.in_h1 = False
        self.h1_parts: list[str] = []
        self.meta: dict[str, str] = {}

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", html.unescape(" ".join(self.buffer)).replace("\xa0", " ")).strip()
        self.buffer = []
        if text:
            self.parts.append(text)

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self._flush(); self.skip += 1; return
        if self.skip:
            return
        if tag == "a":
            href = str(attrs_dict.get("href") or "").strip()
            if href:
                self.hrefs.append(href)
        if tag == "meta":
            key = str(attrs_dict.get("property") or attrs_dict.get("name") or "").strip().casefold()
            value = str(attrs_dict.get("content") or "").strip()
            if key and value:
                self.meta[key] = value
        if tag in BLOCK_TAGS:
            self._flush()
        if tag == "h1":
            self.in_h1 = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            if self.skip: self.skip -= 1
            return
        if self.skip:
            return
        if tag in BLOCK_TAGS:
            self._flush()
        if tag == "h1":
            self.in_h1 = False

    def handle_data(self, data: str) -> None:
        if self.skip or not data.strip():
            return
        self.buffer.append(data)
        if self.in_h1:
            self.h1_parts.append(data)

    def close(self) -> None:
        self._flush(); super().close()

    @property
    def h1(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.h1_parts)).strip()


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def fetch(url: str, timeout: int = 15) -> tuple[bool, int | None, str, str | None]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
        "Accept": "text/html,text/calendar;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed official municipal HTTPS URL
            raw = response.read(); charset = response.headers.get_content_charset() or "utf-8"
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return True, getattr(response, "status", 200), text, None
    except HTTPError as exc:
        return False, exc.code, "", f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, None, "", f"{type(exc).__name__}: {exc}"


def parse(markup: str) -> Parser:
    parser = Parser(); parser.feed(markup); parser.close(); return parser


def parse_day(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def query_occurrences(markup: str, parser: Parser) -> set[date]:
    values: set[date] = set()
    for match in OCCURRENCE_QUERY.finditer(markup):
        day = parse_day(match.group(1))
        if day:
            values.add(day)
    for href in parser.hrefs:
        query = parse_qs(urlparse(urljoin(EVENT_URL, href)).query)
        for value in query.get("occurrence", []):
            day = parse_day(value[:10])
            if day:
                values.add(day)
    return values


def visible_list_occurrences(parser: Parser) -> set[date]:
    values: set[date] = set()
    for block in parser.parts:
        block_norm = norm(block)
        if "rapanui" not in block_norm and "sesion" not in block_norm and "miercoles" not in block_norm:
            continue
        segments = list(DATE_LIST_SEGMENT.finditer(block))
        if not segments:
            continue
        explicit_years = [int(match.group(3)) for match in segments if match.group(3)]
        fallback_year = explicit_years[-1] if explicit_years else None
        if not fallback_year:
            continue
        for match in segments:
            month = MONTHS.get(norm(match.group(2)))
            year = int(match.group(3) or fallback_year)
            if not month:
                continue
            for raw_day in re.findall(r"\d{1,2}", match.group(1)):
                try:
                    values.add(date(year, month, int(raw_day)))
                except ValueError:
                    pass
    return values


def ical_links(parser: Parser) -> list[str]:
    links: list[str] = []
    for href in parser.hrefs:
        absolute = urljoin(EVENT_URL, href)
        lower = absolute.casefold()
        if "method=ical" in lower or lower.endswith(".ics"):
            if absolute not in links:
                links.append(absolute)
    return links[:3]


def unfold_ical(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").split("\n")
    unfolded: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def ical_occurrences(text: str, today: date) -> set[date]:
    values: set[date] = set()
    dtstart: date | None = None
    for line in unfold_ical(text):
        upper = line.upper()
        if upper.startswith("DTSTART"):
            match = re.search(r":(20\d{6})", line)
            if match:
                try:
                    dtstart = datetime.strptime(match.group(1), "%Y%m%d").date(); values.add(dtstart)
                except ValueError:
                    pass
        elif upper.startswith("RDATE"):
            for raw in re.findall(r"20\d{6}", line):
                try: values.add(datetime.strptime(raw, "%Y%m%d").date())
                except ValueError: pass
        elif upper.startswith("RRULE") and dtstart:
            fields = dict(
                part.split("=", 1) for part in line.split(":", 1)[-1].split(";") if "=" in part
            )
            if fields.get("FREQ", "").upper() == "WEEKLY":
                count = int(fields.get("COUNT", "0") or 0)
                until_match = re.match(r"(20\d{6})", fields.get("UNTIL", ""))
                until = datetime.strptime(until_match.group(1), "%Y%m%d").date() if until_match else today + timedelta(days=MAX_HORIZON_DAYS)
                limit = count if count > 0 else 20
                current = dtstart
                for _ in range(limit):
                    if current > until: break
                    values.add(current)
                    current += timedelta(days=7)
    return values


def event_clock(parser: Parser) -> str | None:
    for block in parser.parts:
        block_norm = norm(block)
        if "rapanui" not in block_norm and "hora" not in block_norm:
            continue
        matches = list(TIME_24.finditer(block))
        for match in matches:
            hour = int(match.group(1)); minute = match.group(2)
            if 8 <= hour <= 22:
                return f"{hour:02d}:{minute}"
    return None


def make_event(day: date, title: str, clock: str | None, official_url: str, image_url: str | None) -> dict:
    verified = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    digest = hashlib.sha1(f"{SOURCE_ID}|{day}|{title}".encode()).hexdigest()[:16]
    start = day.isoformat() if not clock else datetime.fromisoformat(f"{day.isoformat()}T{clock}:00").replace(tzinfo=ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    return {
        "id": f"agenda_visitavina_fonck_{digest}",
        "title": title,
        "event_type": "event",
        "primary_category": {"id": "cursos-talleres", "label": "Cursos y talleres"},
        "categories": [{"id": "cursos-talleres", "label": "Cursos y talleres"}],
        "schedule": {
            "mode": "single", "start": start, "end": start, "timezone": TIMEZONE,
            "display_text": f"{day.isoformat()}{' · ' + clock if clock else ''}", "occurrences": [],
            "start_confidence": "explicit", "end_confidence": "explicit",
        },
        "location": {"venue_id": COVERED_SOURCE_ID, "city": CITY, "commune": CITY, "venue": VENUE, "address": ADDRESS, "online": False, "latitude": None, "longitude": None},
        "price": {"is_free": True, "currency": "CLP", "min_amount": 0, "max_amount": 0, "display_text": "Gratis"},
        "links": {"official": official_url, "tickets": None, "registration": None, "source": official_url},
        "organizer": VENUE, "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "source_url": official_url,
        "last_verified_at": verified,
        "public_status": {"source_official": True, "last_verified_at": verified, "registration_open": None, "registration_closed": None, "cancelled": False, "sold_out": None, "price_stage": None, "price_confirmed": True, "information_completeness": "complete" if clock else "partial", "advisory_text": "Ocurrencia futura recuperada desde la cartelera oficial municipal Visita Viña; confirma inscripción y horario en la ficha enlazada."},
        "description": "Sesión futura del Taller de Lengua Rapanui en Museo Fonck, recuperada de la recurrencia explícita de la cartelera municipal.",
        "tags": ["Cursos y talleres", "Museo Fonck", "Visita Viña"], "audience": "Desde 16 años", "registration_requirements": "Inscripción previa según la ficha oficial",
        "image": {"url": image_url, "alt": title if image_url else None},
        "editorial": {"classification": "event", "reason": "official_cross_source:visitavina_fonck", "covered_source_ids": [COVERED_SOURCE_ID], "duration_days": 0},
    }


def key(item: dict) -> tuple[str, str, str]:
    return (norm(item.get("title")), str((item.get("schedule") or {}).get("start") or "")[:10], norm((item.get("location") or {}).get("city")))


def refresh_counts(dataset: dict) -> None:
    events = dataset.get("events") or []
    dataset["counts"] = {
        "total": len(events), "events": sum(x.get("event_type") == "event" for x in events),
        "courses": sum(x.get("event_type") == "course" for x in events),
        "flexible_offers": sum(x.get("event_type") == "flexible_offer" for x in events),
        "programs": sum(x.get("event_type") == "program" for x in events),
    }


def run(no_write: bool = False) -> int:
    today = datetime.now(ZoneInfo(TIMEZONE)).date(); horizon = today + timedelta(days=MAX_HORIZON_DAYS)
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    original = list(dataset.get("events") or [])
    previous = [x for x in original if str((x.get("editorial") or {}).get("reason") or "") == "official_cross_source:visitavina_fonck" and str((x.get("schedule") or {}).get("start") or "")[:10] >= today.isoformat()]
    base = [x for x in original if str((x.get("editorial") or {}).get("reason") or "") != "official_cross_source:visitavina_fonck"]

    ok, status, markup, error = fetch(EVENT_URL)
    parser = parse(markup) if ok else Parser()
    title = parser.h1.strip() if ok else ""
    title_ok = EXPECTED_TITLE in norm(title)
    venue_ok = any("museo fonck" in norm(part) for part in parser.parts) if ok else False
    query_dates = query_occurrences(markup, parser) if ok else set()
    visible_dates = visible_list_occurrences(parser) if ok else set()
    calendar_dates: set[date] = set()
    calendar_results = []
    if ok:
        for calendar_url in ical_links(parser):
            c_ok, c_status, c_text, c_error = fetch(calendar_url, timeout=10)
            calendar_results.append({"url": calendar_url, "fetch_ok": c_ok, "http_status": c_status, "error": c_error})
            if c_ok:
                calendar_dates.update(ical_occurrences(c_text, today))

    discovered = query_dates | visible_dates | calendar_dates
    future = sorted(day for day in discovered if today <= day <= horizon)
    discovery_confident = ok and title_ok and venue_ok and bool(discovered)
    clock = event_clock(parser) if ok else None
    image = parser.meta.get("og:image") if ok else None
    fresh = [make_event(day, title or "Taller de Lengua Rapanui", clock, f"{EVENT_URL}?occurrence={day.isoformat()}", image) for day in future] if discovery_confident else []

    if discovery_confident:
        known = {key(item) for item in base}; source_events = []; duplicates = 0
        for item in fresh:
            if key(item) in known:
                duplicates += 1; continue
            known.add(key(item)); source_events.append(item)
    else:
        source_events = previous; duplicates = 0

    dataset["events"] = sorted(base + source_events, key=lambda x: (str((x.get("schedule") or {}).get("start") or ""), str(x.get("title") or "")))
    refresh_counts(dataset)
    state = "publishing_future_occurrences" if source_events and discovery_confident else ("official_event_expired" if discovery_confident and not future else ("official_event_recurrence_not_resolved" if ok and title_ok and venue_ok else ("official_page_context_mismatch" if ok else "official_page_fetch_error")))
    coverage = ([{"source_id": COVERED_SOURCE_ID, "source_name": VENUE, "covered_by": SOURCE_ID, "reason": "future_recurring_occurrence"}] if source_events else [])
    report = {
        "schema_version": "1.0.0", "generated_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds"),
        "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "covered_source_id": COVERED_SOURCE_ID, "state": state,
        "page": {"url": EVENT_URL, "fetch_ok": ok, "http_status": status, "error": error, "title": title, "title_ok": title_ok, "venue_ok": venue_ok},
        "occurrence_discovery": {"query_dates": sorted(d.isoformat() for d in query_dates), "visible_dates": sorted(d.isoformat() for d in visible_dates), "ical_dates": sorted(d.isoformat() for d in calendar_dates), "future_dates": [d.isoformat() for d in future], "ical_fetches": calendar_results},
        "clock": clock, "events_published": len(source_events), "semantic_duplicates_dropped": duplicates,
        "previous_future_events": len(previous), "coverage": coverage,
        "policy": "Recover only future dates explicitly exposed by the official municipal event page, its occurrence links, visible recurrence text or its iCal export; never infer future sessions from a past start date alone.",
    }
    if no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        DATASET_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover explicit future Museo Fonck occurrences from Visita Viña.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(); raise SystemExit(run(args.no_write))


if __name__ == "__main__":
    main()
