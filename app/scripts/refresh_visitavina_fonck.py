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
LISTING_URL = "https://visitavina.munivina.cl/actividades/"
EVENT_URL = "https://visitavina.munivina.cl/actividad/taller-de-lengua-rapanui-2/"
EVENT_PATH = "/actividad/taller-de-lengua-rapanui-2/"
TIMEZONE = "America/Santiago"
CITY = "Viña del Mar"
VENUE = "Museo Fonck"
ADDRESS = "4 Norte 784, Viña del Mar"
MAX_HORIZON_DAYS = 90
BLOCK_TAGS = {"br", "p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td"}
TIME_RANGE_12H = re.compile(
    r"(?<!\d)(\d{1,2}):([0-5]\d)\s*(am|pm)\s*-\s*(\d{1,2}):([0-5]\d)\s*(am|pm)",
    re.I,
)


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
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed official municipal HTTPS URLs
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
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def listing_occurrences(markup: str) -> dict[date, str]:
    """Return only occurrence links belonging to the exact Museo Fonck workshop slug."""
    parser = parse(markup)
    result: dict[date, str] = {}
    for href in parser.hrefs:
        absolute = urljoin(LISTING_URL, href)
        parsed = urlparse(absolute)
        if parsed.netloc not in {"visitavina.munivina.cl", "www.visitavina.munivina.cl"}:
            continue
        if parsed.path.rstrip("/") != EVENT_PATH.rstrip("/"):
            continue
        for raw in parse_qs(parsed.query).get("occurrence", []):
            day = parse_day(raw)
            if day:
                result[day] = absolute
    return result


def title_ok(title: str) -> bool:
    value = norm(title).split()
    return all(token in value for token in ("taller", "lengua", "rapanui"))


def venue_ok(parser: Parser) -> bool:
    return any("museo fonck" in norm(part) for part in parser.parts[:30])


def to_24h(hour: int, minute: str, meridiem: str) -> str:
    meridiem = meridiem.casefold()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def event_clock(parser: Parser) -> str | None:
    """Prefer the event-specific am/pm range; ignore generic museum opening-hours text."""
    for block in parser.parts[:30]:
        match = TIME_RANGE_12H.search(block)
        if match:
            return to_24h(int(match.group(1)), match.group(2), match.group(3))
    return None


def audience(parser: Parser) -> str | None:
    for part in parser.parts[:40]:
        if re.search(r"desde\s+los?\s+16\s+a[nñ]os", part, re.I):
            return "Desde 16 años"
    return None


def make_event(day: date, title: str, clock: str | None, official_url: str, image_url: str | None, target_audience: str | None) -> dict:
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
        "price": {"is_free": None, "currency": "CLP", "min_amount": None, "max_amount": None, "display_text": "Consultar condiciones"},
        "links": {"official": official_url, "tickets": None, "registration": None, "source": LISTING_URL},
        "organizer": VENUE, "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "source_url": LISTING_URL,
        "last_verified_at": verified,
        "public_status": {"source_official": True, "last_verified_at": verified, "registration_open": None, "registration_closed": None, "cancelled": False, "sold_out": None, "price_stage": None, "price_confirmed": False, "information_completeness": "complete" if clock else "partial", "advisory_text": "Ocurrencia futura recuperada desde la cartelera oficial municipal Visita Viña; confirma acceso y condiciones en la ficha enlazada."},
        "description": "Sesión futura del Taller de Lengua Rapanui en Museo Fonck, recuperada desde un enlace de ocurrencia explícito de la cartelera municipal.",
        "tags": ["Cursos y talleres", "Museo Fonck", "Visita Viña"], "audience": target_audience, "registration_requirements": None,
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

    listing_ok, listing_status, listing_markup, listing_error = fetch(LISTING_URL)
    occurrences = listing_occurrences(listing_markup) if listing_ok else {}
    future_occurrences = {day: url for day, url in occurrences.items() if today <= day <= horizon}

    detail_results = []
    fresh = []
    for day, occurrence_url in sorted(future_occurrences.items()):
        ok, status, markup, error = fetch(occurrence_url)
        parser = parse(markup) if ok else Parser()
        title = parser.h1.strip() if ok else "Taller // Lengua Rapanui"
        t_ok = title_ok(title)
        v_ok = venue_ok(parser) if ok else False
        clock = event_clock(parser) if ok else None
        image = parser.meta.get("og:image") if ok else None
        target_audience = audience(parser) if ok else None
        detail_results.append({
            "date": day.isoformat(), "url": occurrence_url, "fetch_ok": ok, "http_status": status,
            "error": error, "title": title, "title_ok": t_ok, "venue_ok": v_ok, "clock": clock,
        })
        if ok and t_ok and v_ok:
            fresh.append(make_event(day, title, clock, occurrence_url, image, target_audience))

    discovery_confident = listing_ok and bool(occurrences)
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

    if discovery_confident and source_events:
        state = "publishing_future_occurrences"
    elif discovery_confident and not future_occurrences:
        state = "official_listing_no_future_occurrences"
    elif discovery_confident:
        state = "future_occurrence_detail_not_confirmed"
    elif listing_ok:
        state = "official_listing_event_not_found"
    elif previous:
        state = "official_listing_fetch_error_previous_events_preserved"
    else:
        state = "official_listing_fetch_error"

    coverage = ([{"source_id": COVERED_SOURCE_ID, "source_name": VENUE, "covered_by": SOURCE_ID, "reason": "future_recurring_occurrence"}] if source_events else [])
    report = {
        "schema_version": "1.0.0", "generated_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds"),
        "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "covered_source_id": COVERED_SOURCE_ID, "state": state,
        "listing": {"url": LISTING_URL, "fetch_ok": listing_ok, "http_status": listing_status, "error": listing_error},
        "occurrence_discovery": {
            "all_dates": [day.isoformat() for day in sorted(occurrences)],
            "future_dates": [day.isoformat() for day in sorted(future_occurrences)],
            "method": "exact_event_slug_occurrence_links",
        },
        "details": detail_results, "events_published": len(source_events), "semantic_duplicates_dropped": duplicates,
        "previous_future_events": len(previous), "coverage": coverage,
        "policy": "Publish only dates exposed in occurrence links for the exact Museo Fonck workshop slug on the official Visita Viña activities listing; unrelated occurrence links, generic opening hours and iCal ambiguity are ignored.",
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
