from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
REPORT_PATH = ROOT / "app/data/quality/balmaceda-valpo.json"
SOURCE_ID = "balmaceda_arte_joven_valpo_official"
COVERED_SOURCE_ID = "balmaceda_arte_joven_valpo"
SOURCE_NAME = "Balmaceda Arte Joven Valparaíso"
TIMEZONE = "America/Santiago"
CITY = "Valparaíso"
VENUE = "Balmaceda Arte Joven Valparaíso"
ADDRESS = "Santa Isabel 739, Cerro Alegre, Valparaíso"
BASE_URL = "https://www.balmacedartejoven.cl/"
LANDING_URLS = [
    BASE_URL,
    "https://www.balmacedartejoven.cl/sedes/sede-valparaiso/",
    "https://www.balmacedartejoven.cl/sedes/sede-valparaiso/talleres-valparaiso/",
    "https://www.balmacedartejoven.cl/programacion/",
]
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MONTH_PATTERN = "|".join(MONTHS)
DATE_TEXT = re.compile(
    rf"(?:(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)\s+)?"
    rf"(\d{{1,2}})\s+de\s+({MONTH_PATTERN})(?:\s+(?:de\s+)?(20\d{{2}}))?",
    re.I,
)
RANGE_TEXT = re.compile(
    rf"(\d{{1,2}})\s+(?:al|a)\s+(\d{{1,2}})\s+de\s+({MONTH_PATTERN})(?:\s+(?:de\s+)?(20\d{{2}}))?",
    re.I,
)
TIME_TEXT = re.compile(r"(?:a\s+las|desde\s+las|a\s+partir\s+de\s+las)\s*(\d{1,2})[:.]([0-5]\d)", re.I)
BLOCK_TAGS = {"br", "p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td"}
VALPO_MARKERS = (
    "balmaceda arte joven valparaiso", "baj valpo", "sede valparaiso", "cerro alegre",
    "santa isabel 739", "galeria balmaceda arte joven valparaiso",
)
FUTURE_MARKERS = (
    "se realizara", "realizara", "se llevara a cabo", "inaugura", "inauguracion", "invita",
    "presenta", "presentara", "tendra lugar", "abre inscripciones", "inscripciones abiertas",
    "comienza", "inicia", "muestra abierta", "concierto", "taller", "exposicion",
)
CANCEL_MARKERS = ("suspendid", "cancelad", "se suspende", "se cancela")
CONTENT_PATH_MARKERS = ("/noticias/", "/talleres/", "/programacion/")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.tokens: list[dict[str, str | None]] = []
        self.buffer: list[str] = []
        self.current_href: str | None = None
        self.skip = 0
        self.in_h1 = False
        self.h1_parts: list[str] = []
        self.meta: dict[str, str] = {}

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", html.unescape(" ".join(self.buffer)).replace("\xa0", " ")).strip()
        self.buffer = []
        if text:
            self.parts.append(text)
            self.tokens.append({"text": text, "href": self.current_href})

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
        if tag == "a":
            self._flush(); self.current_href = attrs_dict.get("href")
        elif tag in BLOCK_TAGS:
            self._flush()
        if tag == "h1":
            self.in_h1 = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            if self.skip: self.skip -= 1
            return
        if self.skip:
            return
        if tag == "a":
            self._flush(); self.current_href = None
        elif tag in BLOCK_TAGS:
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


def fetch(url: str) -> tuple[bool, int | None, str, str | None]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310 - configured official HTTPS URLs
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


def parse(markup: str) -> PageParser:
    parser = PageParser(); parser.feed(markup); parser.close(); return parser


def as_published_day(parser: PageParser) -> date | None:
    raw = parser.meta.get("article:published_time") or parser.meta.get("date") or parser.meta.get("datepublished")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", raw)
        if not match:
            return None
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None


def discover_links(markup: str) -> list[str]:
    parser = parse(markup); found: list[str] = []; seen: set[str] = set()
    for token in parser.tokens:
        href = str(token.get("href") or "").strip()
        if not href:
            continue
        url = urljoin(BASE_URL, href); parsed = urlparse(url)
        if parsed.netloc not in {"balmacedartejoven.cl", "www.balmacedartejoven.cl"}:
            continue
        if not any(marker in parsed.path for marker in CONTENT_PATH_MARKERS):
            continue
        canonical = f"https://www.balmacedartejoven.cl{parsed.path}"
        if canonical not in seen and canonical not in LANDING_URLS:
            seen.add(canonical); found.append(canonical)
    return found


def infer_year(month: int, today: date, published: date | None, explicit: str | None) -> int | None:
    if explicit:
        return int(explicit)
    if not published or abs((today - published).days) > 180:
        return None
    year = published.year
    candidate = date(year, month, 1)
    if candidate < published - timedelta(days=45) and month <= 2 and published.month >= 11:
        year += 1
    return year


def same_block_candidates(parser: PageParser, today: date) -> list[tuple[date, date, str | None, str]]:
    result: list[tuple[date, date, str | None, str]] = []
    published = as_published_day(parser)
    for block in parser.parts:
        block_norm = norm(block)
        if not any(marker in block_norm for marker in VALPO_MARKERS):
            continue
        if any(marker in block_norm for marker in CANCEL_MARKERS):
            continue
        if not any(marker in block_norm for marker in FUTURE_MARKERS):
            continue
        range_match = RANGE_TEXT.search(block)
        if range_match:
            month = MONTHS.get(norm(range_match.group(3))); year = infer_year(month or 0, today, published, range_match.group(4)) if month else None
            if month and year:
                try:
                    start = date(year, month, int(range_match.group(1))); end = date(year, month, int(range_match.group(2)))
                except ValueError:
                    continue
                if end >= today:
                    time_match = TIME_TEXT.search(block)
                    clock = f"{int(time_match.group(1)):02d}:{time_match.group(2)}" if time_match else None
                    result.append((start, end, clock, block))
            continue
        for match in DATE_TEXT.finditer(block):
            month = MONTHS.get(norm(match.group(3))); year = infer_year(month or 0, today, published, match.group(4)) if month else None
            if not month or not year:
                continue
            try:
                start = date(year, month, int(match.group(2)))
            except ValueError:
                continue
            if start < today:
                continue
            time_match = TIME_TEXT.search(block[match.start():match.end() + 180])
            clock = f"{int(time_match.group(1)):02d}:{time_match.group(2)}" if time_match else None
            result.append((start, start, clock, block))
    unique: dict[tuple[str, str, str | None], tuple[date, date, str | None, str]] = {}
    for row in result:
        unique[(row[0].isoformat(), row[1].isoformat(), row[2])] = row
    return list(unique.values())


def category_for(title: str, body: str) -> tuple[str, str]:
    text = norm(f"{title} {body}")
    if "exposicion" in text or "galeria" in text: return "exposiciones", "Exposiciones"
    if any(x in text for x in ("concierto", "musica", "recital", "banda", "sonidos de casa")): return "musica", "Música"
    if any(x in text for x in ("teatro", "obra", "dramaturgia")): return "teatro", "Teatro"
    if any(x in text for x in ("taller", "laboratorio", "inscripciones")): return "cursos-talleres", "Cursos y talleres"
    return "cultura", "Cultura"


def make_event(title: str, start: date, end: date, clock: str | None, url: str, image: str | None, body: str) -> dict:
    category_id, category_label = category_for(title, body)
    verified = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    digest = hashlib.sha1(f"{SOURCE_ID}|{title}|{start}|{end}|{clock or ''}".encode()).hexdigest()[:16]
    start_value = start.isoformat() if not clock else datetime.fromisoformat(f"{start.isoformat()}T{clock}:00").replace(tzinfo=ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    end_value = end.isoformat() if end != start else start_value
    free = any(x in norm(body) for x in ("entrada liberada", "entrada gratuita", "actividad gratuita", "gratuito", "gratuita"))
    return {
        "id": f"agenda_balmaceda_valpo_{digest}", "title": title, "event_type": "event",
        "primary_category": {"id": category_id, "label": category_label},
        "categories": [{"id": category_id, "label": category_label}],
        "schedule": {
            "mode": "multi_day" if end != start else "single", "start": start_value, "end": end_value,
            "timezone": TIMEZONE, "display_text": f"{start} – {end}" if end != start else f"{start}{' · ' + clock if clock else ''}",
            "occurrences": [], "start_confidence": "explicit", "end_confidence": "explicit",
        },
        "location": {"venue_id": COVERED_SOURCE_ID, "city": CITY, "commune": CITY, "venue": VENUE, "address": ADDRESS, "online": False, "latitude": None, "longitude": None},
        "price": {"is_free": True if free else None, "currency": "CLP", "min_amount": 0 if free else None, "max_amount": 0 if free else None, "display_text": "Entrada liberada" if free else "Consultar condiciones"},
        "links": {"official": url, "tickets": None, "registration": None, "source": url},
        "organizer": SOURCE_NAME, "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "source_url": url,
        "last_verified_at": verified,
        "public_status": {"source_official": True, "last_verified_at": verified, "registration_open": None, "registration_closed": None, "cancelled": False, "sold_out": None, "price_stage": None, "price_confirmed": free, "information_completeness": "partial", "advisory_text": "Confirma horario, acceso y condiciones en la publicación oficial de BAJ Valparaíso."},
        "description": "Actividad futura con fecha explícita publicada por Balmaceda Arte Joven Valparaíso.",
        "tags": [category_label, SOURCE_NAME], "audience": None, "registration_requirements": None,
        "image": {"url": image, "alt": title if image else None},
        "editorial": {"classification": "event", "reason": "official_source:balmaceda_arte_joven_valpo", "covered_source_ids": [COVERED_SOURCE_ID], "duration_days": max(0, (end - start).days)},
    }


def key(item: dict) -> tuple[str, str, str]:
    return (norm(item.get("title")), str((item.get("schedule") or {}).get("start") or "")[:10], norm((item.get("location") or {}).get("city")))


def duplicate(candidate: dict, existing: list[dict]) -> bool:
    ctitle, cday, ccity = key(candidate)
    for other in existing:
        otitle, oday, ocity = key(other)
        if cday != oday or ccity != ocity or not otitle:
            continue
        if ctitle == otitle: return True
        if (ctitle in otitle or otitle in ctitle) and min(len(ctitle), len(otitle)) >= 12: return True
        if SequenceMatcher(None, ctitle, otitle).ratio() >= 0.86: return True
    return False


def refresh_counts(dataset: dict) -> None:
    events = dataset.get("events") or []
    dataset["counts"] = {
        "total": len(events), "events": sum(x.get("event_type") == "event" for x in events),
        "courses": sum(x.get("event_type") == "course" for x in events),
        "flexible_offers": sum(x.get("event_type") == "flexible_offer" for x in events),
        "programs": sum(x.get("event_type") == "program" for x in events),
    }


def run(no_write: bool = False) -> int:
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    base = [x for x in dataset.get("events") or [] if str((x.get("editorial") or {}).get("reason") or "") != "official_source:balmaceda_arte_joven_valpo"]

    landing_results = []; links: list[str] = []; seen: set[str] = set()
    for url in LANDING_URLS:
        ok, status, markup, error = fetch(url)
        landing_results.append({"url": url, "fetch_ok": ok, "http_status": status, "error": error})
        if ok:
            for link in discover_links(markup):
                if link not in seen:
                    seen.add(link); links.append(link)

    recent_pages = 0; scanned = 0; failures = []; fresh: list[dict] = []; recent_titles: list[str] = []
    cutoff = today - timedelta(days=180)
    for url in links[:40]:
        ok, status, markup, error = fetch(url)
        if not ok:
            failures.append({"url": url, "http_status": status, "error": error}); continue
        scanned += 1
        parser = parse(markup); published = as_published_day(parser)
        body = " ".join(parser.parts); title = parser.h1 or (parser.parts[0] if parser.parts else "")
        page_norm = norm(body)
        valpo_page = any(marker in page_norm for marker in VALPO_MARKERS)
        if valpo_page and published and published >= cutoff:
            recent_pages += 1
            if title: recent_titles.append(title)
        if not valpo_page or not title:
            continue
        image = parser.meta.get("og:image")
        for start, end, clock, block in same_block_candidates(parser, today):
            fresh.append(make_event(title, start, end, clock, url, image, block))

    source_events = []; duplicates = 0; ids = set()
    for candidate in fresh:
        if candidate["id"] in ids: continue
        ids.add(candidate["id"])
        if duplicate(candidate, base + source_events):
            duplicates += 1; continue
        source_events.append(candidate)

    dataset["events"] = sorted(base + source_events, key=lambda x: (str((x.get("schedule") or {}).get("start") or ""), str(x.get("title") or "")))
    refresh_counts(dataset)
    site_reachable = any(x["fetch_ok"] for x in landing_results)
    official_recent_activity = recent_pages > 0 or bool(source_events)
    state = "publishing_explicit_future_events" if source_events else ("official_recent_activity_no_publishable_future_dates" if official_recent_activity else ("official_site_reachable_no_recent_activity_detected" if site_reachable else "official_site_fetch_error"))
    report = {
        "schema_version": "1.0.0", "generated_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds"),
        "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "covered_source_id": COVERED_SOURCE_ID,
        "source_role": "official_primary_source", "state": state, "landings": landing_results,
        "links_discovered": len(links), "pages_scanned": scanned, "page_fetch_failures": failures,
        "recent_valpo_pages": recent_pages, "recent_valpo_titles": recent_titles[:12],
        "future_dated_candidates": len(fresh), "events_published": len(source_events), "semantic_duplicates_dropped": duplicates,
        "coverage": ([{"source_id": COVERED_SOURCE_ID, "source_name": SOURCE_NAME, "covered_by": SOURCE_ID, "reason": "official_recent_activity"}] if official_recent_activity else []),
        "policy": "Only recent official Valparaíso content can cover the zero source; publication requires an explicit future date and Valparaíso/BAJ context in the same content block. Historical pages never create current events.",
    }
    if no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        DATASET_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover Balmaceda Arte Joven Valparaíso from its official website.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(); raise SystemExit(run(args.no_write))


if __name__ == "__main__":
    main()
