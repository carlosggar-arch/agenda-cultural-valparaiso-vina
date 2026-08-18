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
REPORT_PATH = ROOT / "app/data/quality/visitavina-estadio-espanol.json"
SOURCE_ID = "visitavina_estadio_espanol_recovery"
SOURCE_NAME = "Visita Viña — Estadio Español"
COVERED_SOURCE_ID = "estadio_espanol_recreo"
LISTING_URL = "https://visitavina.munivina.cl/actividades/"
TIMEZONE = "America/Santiago"
CITY = "Viña del Mar"
VENUE = "Estadio Español"
ADDRESS = "Alonso de Ercilla 795, Viña del Mar"
MAX_HORIZON_DAYS = 60
MAX_DETAIL_FETCHES = 12
BLOCK_TAGS = {"br", "p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td"}
TIME_RANGE_12H = re.compile(
    r"(?<!\d)(\d{1,2}):([0-5]\d)\s*(am|pm)\s*(?:-|–|—|a)\s*(\d{1,2}):([0-5]\d)\s*(am|pm)",
    re.I,
)
TIME_SINGLE_12H = re.compile(r"(?<!\d)(\d{1,2}):([0-5]\d)\s*(am|pm)", re.I)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


class DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.buffer: list[str] = []
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
            if self.skip:
                self.skip -= 1
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


class ListingParser(HTMLParser):
    """Capture event links plus nearby text until the next event link.

    Visita Viña renders each activity title as an occurrence-specific link, followed by
    the venue name. We use only the exact venue text to shortlist links; date/time are
    still confirmed from the occurrence link/detail page.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.records: list[dict] = []
        self.current: dict | None = None
        self.in_event_anchor = False
        self.skip = 0

    def _finalize(self) -> None:
        if not self.current:
            return
        self.current["text"] = re.sub(r"\s+", " ", " ".join(self.current.get("parts") or [])).strip()
        self.current.pop("parts", None)
        self.records.append(self.current)
        self.current = None

    @staticmethod
    def _is_event_href(href: str) -> bool:
        parsed = urlparse(urljoin(LISTING_URL, href))
        return parsed.netloc in {"visitavina.munivina.cl", "www.visitavina.munivina.cl"} and "/actividad/" in parsed.path and "occurrence=" in parsed.query

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip += 1; return
        if self.skip:
            return
        if tag == "a":
            href = str(dict(attrs).get("href") or "").strip()
            if href and self._is_event_href(href):
                self._finalize()
                self.current = {"href": urljoin(LISTING_URL, href), "parts": []}
                self.in_event_anchor = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            if self.skip:
                self.skip -= 1
            return
        if self.skip:
            return
        if tag == "a" and self.in_event_anchor:
            self.in_event_anchor = False

    def handle_data(self, data: str) -> None:
        if self.skip or not self.current or not data.strip():
            return
        self.current["parts"].append(data.strip())

    def close(self) -> None:
        self._finalize(); super().close()


def fetch(url: str, timeout: int = 12) -> tuple[bool, int | None, str, str | None]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed official municipal HTTPS source
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


def parse_day_from_url(url: str) -> date | None:
    values = parse_qs(urlparse(url).query).get("occurrence", [])
    if not values:
        return None
    try:
        return date.fromisoformat(values[0][:10])
    except ValueError:
        return None


def listing_candidates(markup: str, today: date, horizon: date) -> list[dict]:
    parser = ListingParser(); parser.feed(markup); parser.close()
    candidates: list[dict] = []
    seen: set[str] = set()
    for record in parser.records:
        url = str(record.get("href") or "")
        day = parse_day_from_url(url)
        if not day or day < today or day > horizon or url in seen:
            continue
        context = norm(record.get("text"))
        if "estadio espanol" not in context:
            continue
        seen.add(url)
        candidates.append({"date": day, "url": url, "listing_context": record.get("text") or ""})
    return candidates[:MAX_DETAIL_FETCHES]


def parse_detail(markup: str) -> DetailParser:
    parser = DetailParser(); parser.feed(markup); parser.close(); return parser


def venue_ok(parser: DetailParser) -> bool:
    return any("estadio espanol" in norm(part) for part in parser.parts[:50])


def to_24h(hour: int, minute: str, meridiem: str) -> str:
    meridiem = meridiem.casefold()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def event_times(parser: DetailParser) -> tuple[str | None, str | None]:
    for block in parser.parts[:40]:
        match = TIME_RANGE_12H.search(block)
        if match:
            return (
                to_24h(int(match.group(1)), match.group(2), match.group(3)),
                to_24h(int(match.group(4)), match.group(5), match.group(6)),
            )
    for block in parser.parts[:40]:
        match = TIME_SINGLE_12H.search(block)
        if match:
            return to_24h(int(match.group(1)), match.group(2), match.group(3)), None
    return None, None


def category_for(title: str) -> tuple[str, str]:
    value = norm(title)
    if any(word in value for word in ("concierto", "musica", "orquesta", "recital")):
        return "musica", "Música"
    if any(word in value for word in ("humor", "stand up", "comedia")):
        return "teatro-artes-escenicas", "Teatro y artes escénicas"
    return "cultura", "Cultura"


def make_event(day: date, title: str, start_clock: str | None, end_clock: str | None, official_url: str, image_url: str | None) -> dict:
    verified = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    digest = hashlib.sha1(f"{SOURCE_ID}|{day}|{title}".encode()).hexdigest()[:16]
    start = day.isoformat() if not start_clock else datetime.fromisoformat(f"{day.isoformat()}T{start_clock}:00").replace(tzinfo=ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    end = start
    if end_clock:
        end = datetime.fromisoformat(f"{day.isoformat()}T{end_clock}:00").replace(tzinfo=ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    category_id, category_label = category_for(title)
    return {
        "id": f"agenda_visitavina_estadio_espanol_{digest}",
        "title": title,
        "event_type": "event",
        "primary_category": {"id": category_id, "label": category_label},
        "categories": [{"id": category_id, "label": category_label}],
        "schedule": {
            "mode": "single", "start": start, "end": end, "timezone": TIMEZONE,
            "display_text": f"{day.isoformat()}{' · ' + start_clock if start_clock else ''}{'–' + end_clock if end_clock else ''}",
            "occurrences": [], "start_confidence": "explicit", "end_confidence": "explicit" if end_clock else "inferred_same_as_start",
        },
        "location": {"venue_id": COVERED_SOURCE_ID, "city": CITY, "commune": CITY, "venue": VENUE, "address": ADDRESS, "online": False, "latitude": None, "longitude": None},
        "price": {"is_free": None, "currency": "CLP", "min_amount": None, "max_amount": None, "display_text": "Consultar condiciones"},
        "links": {"official": official_url, "tickets": None, "registration": None, "source": LISTING_URL},
        "organizer": None, "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "source_url": LISTING_URL,
        "last_verified_at": verified,
        "public_status": {"source_official": True, "last_verified_at": verified, "registration_open": None, "registration_closed": None, "cancelled": False, "sold_out": None, "price_stage": None, "price_confirmed": False, "information_completeness": "complete" if start_clock else "partial", "advisory_text": "Evento futuro recuperado desde la cartelera oficial municipal Visita Viña; confirma condiciones en la ficha enlazada."},
        "description": f"Actividad futura en {VENUE}, recuperada desde una ocurrencia explícita de la cartelera oficial Visita Viña.",
        "tags": [category_label, VENUE, "Visita Viña"], "audience": None, "registration_requirements": None,
        "image": {"url": image_url, "alt": title if image_url else None},
        "editorial": {"classification": "event", "reason": "official_cross_source:visitavina_estadio_espanol", "covered_source_ids": [COVERED_SOURCE_ID], "duration_days": 0},
    }


def key(item: dict) -> tuple[str, str, str]:
    title = norm(item.get("title"))
    title = re.sub(r"\b(concierto|musica|show|humor)\b", "", title).strip()
    return (title, str((item.get("schedule") or {}).get("start") or "")[:10], norm((item.get("location") or {}).get("venue") or (item.get("location") or {}).get("city")))


def refresh_counts(dataset: dict) -> None:
    events = dataset.get("events") or []
    dataset["counts"] = {
        "total": len(events), "events": sum(x.get("event_type") == "event" for x in events),
        "courses": sum(x.get("event_type") == "course" for x in events),
        "flexible_offers": sum(x.get("event_type") == "flexible_offer" for x in events),
        "programs": sum(x.get("event_type") == "program" for x in events),
    }


def run(no_write: bool = False) -> int:
    now = datetime.now(ZoneInfo(TIMEZONE)); today = now.date(); horizon = today + timedelta(days=MAX_HORIZON_DAYS)
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    original = list(dataset.get("events") or [])
    reason = "official_cross_source:visitavina_estadio_espanol"
    previous = [x for x in original if str((x.get("editorial") or {}).get("reason") or "") == reason and str((x.get("schedule") or {}).get("start") or "")[:10] >= today.isoformat()]
    base = [x for x in original if str((x.get("editorial") or {}).get("reason") or "") != reason]

    listing_ok, listing_status, listing_markup, listing_error = fetch(LISTING_URL)
    candidates = listing_candidates(listing_markup, today, horizon) if listing_ok else []
    details = []
    fresh = []
    for candidate in candidates:
        ok, status, markup, error = fetch(candidate["url"], timeout=10)
        parser = parse_detail(markup) if ok else DetailParser()
        title = parser.h1.strip() if ok else ""
        v_ok = venue_ok(parser) if ok else False
        start_clock, end_clock = event_times(parser) if ok else (None, None)
        image = parser.meta.get("og:image") if ok else None
        details.append({
            "date": candidate["date"].isoformat(), "url": candidate["url"], "fetch_ok": ok,
            "http_status": status, "error": error, "title": title, "venue_ok": v_ok,
            "start_clock": start_clock, "end_clock": end_clock, "listing_context": candidate["listing_context"],
        })
        if ok and title and v_ok:
            fresh.append(make_event(candidate["date"], title, start_clock, end_clock, candidate["url"], image))

    discovery_confident = listing_ok
    if discovery_confident:
        known = {key(item) for item in base}; source_events = []; duplicates = 0
        for item in fresh:
            item_key = key(item)
            if item_key in known:
                duplicates += 1; continue
            known.add(item_key); source_events.append(item)
    else:
        source_events = previous; duplicates = 0

    dataset["events"] = sorted(base + source_events, key=lambda x: (str((x.get("schedule") or {}).get("start") or ""), str(x.get("title") or "")))
    refresh_counts(dataset)

    if source_events:
        state = "publishing_future_events"
    elif listing_ok and candidates:
        state = "future_candidate_detail_not_confirmed"
    elif listing_ok:
        state = "official_listing_no_future_estadio_espanol_events"
    elif previous:
        state = "official_listing_fetch_error_previous_events_preserved"
    else:
        state = "official_listing_fetch_error"

    coverage = ([{"source_id": COVERED_SOURCE_ID, "source_name": "Estadio Español Recreo", "covered_by": SOURCE_ID, "reason": "future_official_municipal_event"}] if source_events else [])
    report = {
        "schema_version": "1.0.0", "generated_at": now.isoformat(timespec="seconds"),
        "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "covered_source_id": COVERED_SOURCE_ID, "state": state,
        "listing": {"url": LISTING_URL, "fetch_ok": listing_ok, "http_status": listing_status, "error": listing_error},
        "candidates": [{**row, "date": row["date"].isoformat()} for row in candidates],
        "details": details, "events_published": len(source_events), "semantic_duplicates_dropped": duplicates,
        "previous_future_events": len(previous), "coverage": coverage,
        "policy": "Publish only future occurrence-specific links from the official Visita Viña activities listing whose own listing context and detail page identify Estadio Español; never infer dates or promote historical Instagram content.",
    }
    if no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        DATASET_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover official future Estadio Español events from Visita Viña.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(); raise SystemExit(run(args.no_write))


if __name__ == "__main__":
    main()
