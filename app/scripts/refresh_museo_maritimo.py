from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "agenda_web.json"
QUALITY = ROOT / "app/data/quality/museo-maritimo.json"
SOURCE_ID = "museo_maritimo_nacional"
SOURCE_NAME = "Museo Marítimo Nacional"
PROGRAM_URL = "https://museomaritimo.cl/programacion/"
ARCHIVE_URLS = [
    "https://museomaritimo.cl/author/capacitador/",
    "https://museomaritimo.cl/author/capacitador/page/2/",
    "https://museomaritimo.cl/author/capacitador/page/3/",
]
TIMEZONE = "America/Santiago"
CITY = "Valparaíso"
VENUE = "Museo Marítimo Nacional"
ADDRESS = "Paseo 21 de Mayo 45, Cerro Artillería, Valparaíso"
MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
MONTH_PATTERN = "|".join(MONTHS)
DATE_TEXT = re.compile(
    rf"(?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)?\s*"
    rf"(\d{{1,2}})\s+de\s+({MONTH_PATTERN})(?:\s+de\s+(20\d{{2}}))?",
    re.I,
)
TIME_TEXT = re.compile(r"(?:entre\s+las|desde\s+las|a\s+las)\s*(\d{1,2})[:.]([0-5]\d)", re.I)
ARTICLE_PATH = re.compile(r"/20\d{2}/\d{2}/\d{2}/[^/?#]+/?$")
BLOCK_TAGS = {"br", "p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td", "button"}
LOCAL_MARKERS = (
    "paseo 21 de mayo",
    "cerro artilleria",
    "dependencias del museo maritimo nacional",
    "en el museo maritimo nacional",
)


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
        self.og_image: str | None = None

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", html.unescape(" ".join(self.buffer)).replace("\xa0", " ")).strip()
        self.buffer = []
        if text:
            self.parts.append(text)
            self.tokens.append({"text": text, "href": self.current_href})

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self._flush()
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "meta" and str(attrs_dict.get("property") or "").casefold() == "og:image":
            content = str(attrs_dict.get("content") or "").strip()
            if content:
                self.og_image = content
        if tag == "a":
            self._flush()
            self.current_href = attrs_dict.get("href")
        elif tag in BLOCK_TAGS:
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
        if tag == "a":
            self._flush()
            self.current_href = None
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
        self._flush()
        super().close()

    @property
    def h1(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.h1_parts)).strip()


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


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
        with urlopen(request, timeout=30) as response:  # nosec B310 - fixed official HTTPS URLs
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


def parse(markup: str) -> PageParser:
    parser = PageParser()
    parser.feed(markup)
    parser.close()
    return parser


def month_year(month: int, today: date) -> int | None:
    if month >= today.month:
        return today.year
    if today.month >= 11 and month <= 2:
        return today.year + 1
    return None


def monthly_program_items(text: list[str], today: date) -> list[dict]:
    items: list[dict] = []
    seen: set[tuple[int, int, str]] = set()
    for index, value in enumerate(text[:-1]):
        month = MONTHS.get(norm(value))
        if not month:
            continue
        year = month_year(month, today)
        if year is None:
            continue
        for candidate in text[index + 1:index + 4]:
            candidate_norm = norm(candidate)
            if "exposicion" not in candidate_norm:
                continue
            title = re.sub(r"^EXPOSICI[ÓO]N\s+(?:TEMPORAL\s+|DIGITAL\s+|TEMPORAL\s+DIGITAL\s+)?", "", candidate, flags=re.I).strip(" \"'“”")
            if len(title) < 4:
                continue
            signature = (year, month, norm(title))
            if signature in seen:
                break
            seen.add(signature)
            items.append({
                "title": title,
                "month": month,
                "year": year,
                "publishable": False,
                "reason": "month_only_no_explicit_start_end",
            })
            break
    return items


def article_links(markup: str) -> list[str]:
    parser = parse(markup)
    result: list[str] = []
    seen: set[str] = set()
    for token in parser.tokens:
        href = str(token.get("href") or "").strip()
        if not href:
            continue
        url = urljoin(PROGRAM_URL, href)
        parsed = urlparse(url)
        if parsed.netloc not in {"museomaritimo.cl", "www.museomaritimo.cl"}:
            continue
        if not ARTICLE_PATH.search(parsed.path):
            continue
        canonical = f"https://museomaritimo.cl{parsed.path}"
        if canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
    return result


def category_for(title: str, body: str) -> tuple[str, str]:
    value = norm(f"{title} {body}")
    if "exposicion" in value:
        return "exposiciones", "Exposiciones"
    if any(term in value for term in ("concierto", "orquesta", "banda de musicos", "recital")):
        return "musica", "Música"
    if any(term in value for term in ("obra teatral", "obra de teatro", "teatro")):
        return "teatro", "Teatro"
    if "taller" in value:
        return "cursos-talleres", "Cursos y talleres"
    return "museos", "Museos"


def make_event(title: str, start: date, clock: str | None, article_url: str, image_url: str | None, body: str) -> dict:
    verified = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    digest = hashlib.sha1(f"{SOURCE_ID}|{start}|{clock or ''}|{title}".encode()).hexdigest()[:16]
    category_id, category_label = category_for(title, body)
    if clock:
        start_iso = datetime.fromisoformat(f"{start.isoformat()}T{clock}:00").replace(tzinfo=ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    else:
        start_iso = start.isoformat()
    body_norm = norm(body)
    free = any(marker in body_norm for marker in ("entrada liberada", "entrada gratuita", "actividad gratuita", "jornada familiar gratuita"))
    price_text = "Entrada liberada" if free else "Consultar condiciones"
    return {
        "id": f"agenda_{SOURCE_ID}_{digest}",
        "title": title.strip(),
        "event_type": "event",
        "primary_category": {"id": category_id, "label": category_label},
        "categories": [{"id": category_id, "label": category_label}],
        "schedule": {
            "mode": "single",
            "start": start_iso,
            "end": start_iso,
            "timezone": TIMEZONE,
            "display_text": f"{start.isoformat()}{' · ' + clock if clock else ''}",
            "occurrences": [],
            "start_confidence": "explicit",
            "end_confidence": "explicit",
        },
        "location": {
            "venue_id": SOURCE_ID,
            "city": CITY,
            "commune": CITY,
            "venue": VENUE,
            "address": ADDRESS,
            "online": False,
            "latitude": None,
            "longitude": None,
        },
        "price": {
            "is_free": True if free else None,
            "currency": "CLP",
            "min_amount": 0 if free else None,
            "max_amount": 0 if free else None,
            "display_text": price_text,
        },
        "links": {"official": article_url, "tickets": None, "registration": None, "source": PROGRAM_URL},
        "organizer": SOURCE_NAME,
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": PROGRAM_URL,
        "last_verified_at": verified,
        "public_status": {
            "source_official": True,
            "last_verified_at": verified,
            "registration_open": None,
            "registration_closed": None,
            "cancelled": False,
            "sold_out": None,
            "price_stage": None,
            "price_confirmed": free,
            "information_completeness": "partial",
            "advisory_text": "Confirma horario, acceso y condiciones en la publicación oficial del Museo Marítimo Nacional.",
        },
        "description": "Actividad futura con fecha explícita detectada en una publicación oficial del Museo Marítimo Nacional.",
        "tags": [category_label, SOURCE_NAME],
        "audience": None,
        "registration_requirements": None,
        "image": {"url": image_url, "alt": title if image_url else None},
        "editorial": {
            "classification": "event",
            "reason": "official_source:museo_maritimo_nacional",
            "duration_days": 0,
        },
    }


def extract_events_from_article(markup: str, article_url: str, today: date) -> list[dict]:
    parser = parse(markup)
    title = parser.h1 or (parser.parts[0] if parser.parts else "")
    if len(norm(title)) < 4:
        return []
    body = " ".join(parser.parts)
    body_norm = norm(body)
    if "cancelad" in body_norm or "suspendid" in body_norm:
        return []
    if not any(marker in body_norm for marker in LOCAL_MARKERS):
        return []

    result: list[dict] = []
    seen_dates: set[tuple[str, str | None]] = set()
    for match in DATE_TEXT.finditer(body):
        month = MONTHS.get(norm(match.group(2)))
        if not month:
            continue
        year = int(match.group(3) or today.year)
        try:
            start = date(year, month, int(match.group(1)))
        except ValueError:
            continue
        if start < today:
            continue
        context = body[match.start():match.end() + 180]
        time_match = TIME_TEXT.search(context)
        clock = f"{int(time_match.group(1)):02d}:{time_match.group(2)}" if time_match else None
        signature = (start.isoformat(), clock)
        if signature in seen_dates:
            continue
        seen_dates.add(signature)
        result.append(make_event(title, start, clock, article_url, parser.og_image, body))
    return result


def event_day(item: dict) -> str:
    return str((item.get("schedule") or {}).get("start") or "")[:10]


def event_end(item: dict) -> str:
    schedule = item.get("schedule") or {}
    return str(schedule.get("end") or schedule.get("start") or "")[:10]


def semantic_duplicate(candidate: dict, existing: list[dict]) -> bool:
    candidate_title = norm(candidate.get("title"))
    candidate_day = event_day(candidate)
    for other in existing:
        if event_day(other) != candidate_day:
            continue
        other_city = norm((other.get("location") or {}).get("city"))
        if other_city != "valparaiso":
            continue
        other_title = norm(other.get("title"))
        if not other_title:
            continue
        if candidate_title == other_title:
            return True
        if candidate_title in other_title or other_title in candidate_title:
            if min(len(candidate_title), len(other_title)) >= 12:
                return True
        if SequenceMatcher(None, candidate_title, other_title).ratio() >= 0.86:
            return True
    return False


def refresh_counts(dataset: dict) -> None:
    events = dataset.get("events") or []
    dataset["counts"] = {
        "total": len(events),
        "events": sum(item.get("event_type") == "event" for item in events),
        "courses": sum(item.get("event_type") == "course" for item in events),
        "flexible_offers": sum(item.get("event_type") == "flexible_offer" for item in events),
        "programs": sum(item.get("event_type") == "program" for item in events),
    }


def load_dataset() -> dict:
    return json.loads(DATASET.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(no_write: bool = False) -> int:
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    dataset = load_dataset()
    original_events = list(dataset.get("events") or [])
    base = [item for item in original_events if str(item.get("source_id") or "") != SOURCE_ID]
    previous = [item for item in original_events if str(item.get("source_id") or "") == SOURCE_ID and event_end(item) >= today.isoformat()]

    program_ok, program_status, program_markup, program_error = fetch(PROGRAM_URL)
    monthly = monthly_program_items(parse(program_markup).parts, today) if program_ok else []

    archive_results = []
    links: list[str] = []
    seen_links: set[str] = set()
    for archive_url in ARCHIVE_URLS:
        ok, status, markup, error = fetch(archive_url)
        archive_results.append({"url": archive_url, "fetch_ok": ok, "http_status": status, "error": error})
        if not ok:
            continue
        for link in article_links(markup):
            if link not in seen_links:
                seen_links.add(link)
                links.append(link)

    archive_ok = any(item["fetch_ok"] for item in archive_results)
    fresh: list[dict] = []
    article_failures = []
    articles_scanned = 0
    for article_url in links[:30]:
        ok, status, markup, error = fetch(article_url)
        if not ok:
            article_failures.append({"url": article_url, "http_status": status, "error": error})
            continue
        articles_scanned += 1
        fresh.extend(extract_events_from_article(markup, article_url, today))

    candidate_pool = fresh if archive_ok else previous
    source_events: list[dict] = []
    duplicates = 0
    seen_ids: set[str] = set()
    for candidate in candidate_pool:
        candidate_id = str(candidate.get("id") or "")
        if not candidate_id or candidate_id in seen_ids:
            continue
        seen_ids.add(candidate_id)
        if semantic_duplicate(candidate, base + source_events):
            duplicates += 1
            continue
        source_events.append(candidate)

    dataset["events"] = sorted(base + source_events, key=lambda item: (event_day(item), str(item.get("title") or "")))
    refresh_counts(dataset)

    if archive_ok and source_events:
        state = "publishing_explicit_future_events"
    elif archive_ok and monthly:
        state = "official_program_detected_no_explicit_future_dates"
    elif archive_ok:
        state = "no_publishable_future_events"
    elif previous:
        state = "archive_fetch_error_previous_events_preserved"
    else:
        state = "archive_fetch_error"

    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds"),
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_role": "official_primary_source",
        "state": state,
        "program": {
            "url": PROGRAM_URL,
            "fetch_ok": program_ok,
            "http_status": program_status,
            "error": program_error,
            "monthly_items_detected": len(monthly),
            "monthly_items": monthly,
        },
        "archives": archive_results,
        "articles_discovered": len(links),
        "articles_scanned": articles_scanned,
        "article_fetch_failures": article_failures,
        "future_dated_candidates": len(fresh),
        "previous_future_events": len(previous),
        "events_published": len(source_events),
        "semantic_duplicates_dropped": duplicates,
        "policy": "Month-only programme items are monitored but never converted into invented start/end dates; only explicit future dates from official MMN articles are publishable.",
    }

    if no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        save_json(DATASET, dataset)
        save_json(QUALITY, report)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh official Museo Marítimo Nacional events conservatively.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(args.no_write))


if __name__ == "__main__":
    main()
