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
QUALITY = ROOT / "app/data/quality/portaltickets-editorial.json"
SOURCE_ID = "portaltickets_valparaiso"
SOURCE_NAME = "PortalTickets — Región de Valparaíso"
SOURCE_URL = "https://www.portaldisc.com/tickets/R05"
TIMEZONE = "America/Santiago"
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
OUT_OF_SCOPE = {
    "san antonio", "casablanca", "limache", "quilpue", "villa alemana", "quintero", "puchuncavi",
    "concon", "el quisco", "el tabo", "algarrobo", "cartagena", "la ligua", "zapallar", "papudo",
    "olmue", "los andes", "san felipe",
}
VENUE_PREFIX = re.compile(
    r"^(?:teatro|bar|cafe|café|club|espacio|parque|casa|casona|sala|centro cultural|universidad|"
    r"balmaceda|vina stage|viña stage|la colombina|el pasaje|patio|cassot|lemutt|trotamundos|"
    r"los alquinta|ipanema|poseidon|poseidón|emporio|burger bar|a tempo)", re.I,
)
ADDRESS_HINT = re.compile(
    r"\b(?:av\.?|avenida|calle|viana|agua santa|brasil|alemania|antofagasta|eusebio lillo|"
    r"gral\.?|general|carcel|cárcel|ortiz de rozas|socrates|sócrates)\b", re.I,
)
DATE_LONG = re.compile(
    r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"(?:\s+(\d{4}))?.*?(\d{2}:\d{2})", re.I,
)
DATE_NUM = re.compile(r"(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2})")


class PortalTokenParser(HTMLParser):
    BLOCK_TAGS = {"br", "p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td", "button"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[dict[str, str | None]] = []
        self.buffer: list[str] = []
        self.href: str | None = None
        self.skip = 0

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", html.unescape(" ".join(self.buffer)).replace("\xa0", " ")).strip()
        self.buffer = []
        if text:
            self.tokens.append({"text": text, "href": self.href})

    def handle_starttag(self, tag, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._flush(); self.skip += 1; return
        if self.skip:
            return
        if tag == "a":
            self._flush(); self.href = dict(attrs).get("href")
        elif tag in self.BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag) -> None:
        if tag in {"script", "style", "noscript"}:
            if self.skip: self.skip -= 1
            return
        if self.skip:
            return
        if tag == "a":
            self._flush(); self.href = None
        elif tag in self.BLOCK_TAGS:
            self._flush()

    def handle_data(self, data) -> None:
        if not self.skip and data.strip():
            self.buffer.append(data)

    def close(self) -> None:
        self._flush(); super().close()


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def city_from_venue(value: str) -> str | None:
    normalized = norm(value)
    if any(marker in normalized for marker in OUT_OF_SCOPE):
        return None
    if normalized.endswith("vina del mar"):
        return "Viña del Mar"
    if normalized.endswith("valparaiso"):
        return "Valparaíso"
    return None


def out_of_scope(value: str) -> bool:
    normalized = norm(value)
    return any(marker in normalized for marker in OUT_OF_SCOPE)


def looks_like_venue(value: str) -> bool:
    return bool(city_from_venue(value) and VENUE_PREFIX.search(value.strip()))


def bad_title(value: str) -> bool:
    normalized = norm(value)
    if len(normalized) < 6 or out_of_scope(value):
        return True
    if "ticket" in normalized or normalized in {"proximos eventos", "ordenar por fecha", "buscar evento o local", "mas info", "ver mapa"}:
        return True
    if ADDRESS_HINT.search(value) and re.search(r"\b\d{2,5}\b", value) and city_from_venue(value):
        return True
    return False


def parse_date(value: str, today: date) -> tuple[date, str] | None:
    match = DATE_LONG.search(value)
    if match:
        month = MONTHS.get(norm(match.group(2)))
        try:
            day = date(int(match.group(3) or today.year), month, int(match.group(1))) if month else None
        except ValueError:
            day = None
        return (day, match.group(4)) if day else None
    match = DATE_NUM.search(value)
    if match:
        try:
            return datetime.strptime(match.group(1), "%d-%m-%Y").date(), match.group(2)
        except ValueError:
            return None
    return None


def ticket_token(token: dict[str, str | None]) -> bool:
    value = norm(token.get("text"))
    return "tickets aqui" in value or value in {"tickets", "comprar entradas", "entradas"}


def individual_ticket_url(token: dict[str, str | None]) -> str | None:
    href = str(token.get("href") or "").strip()
    if not href or href.startswith(("javascript:", "#")):
        return None
    result = urljoin(SOURCE_URL, href)
    parsed = urlparse(result)
    if parsed.scheme not in {"http", "https"}:
        return None
    if result.rstrip("/") == SOURCE_URL.rstrip("/"):
        return None
    return result


def category_for(title: str) -> tuple[str, str]:
    value = norm(title)
    if any(term in value for term in ("pelicula", "documental", "cortometraje", "largometraje")):
        return "cine", "Cine"
    if any(term in value for term in (
        "concierto", "orquesta", "ensamble", " trio ", "banda", "tributo", " gira ", " tour ", "tocata", " dj ",
        "vinilo", "sonora", "sinfonico", "lanzamiento disco", "quinteto", "cuarteto", "disco", "canciones",
    )):
        return "musica", "Música"
    return "cultura", "Cultura"


def make_event(title: str, start: date, clock: str, venue: str, city: str, ticket_url: str) -> dict:
    verified = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    digest = hashlib.sha1(f"{SOURCE_ID}|{start}|{clock}|{title}|{city}".encode()).hexdigest()[:16]
    category_id, category_label = category_for(title)
    start_iso = datetime.fromisoformat(f"{start.isoformat()}T{clock}:00").replace(tzinfo=ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    return {
        "id": f"agenda_{SOURCE_ID}_{digest}",
        "title": title.strip(),
        "event_type": "event",
        "primary_category": {"id": category_id, "label": category_label},
        "categories": [{"id": category_id, "label": category_label}],
        "schedule": {
            "mode": "single", "start": start_iso, "end": start_iso, "timezone": TIMEZONE,
            "display_text": f"{start.isoformat()} · {clock}", "occurrences": [],
            "start_confidence": "explicit", "end_confidence": "explicit",
        },
        "location": {
            "venue_id": SOURCE_ID, "city": city, "commune": city, "venue": venue.strip(), "address": None,
            "online": False, "latitude": None, "longitude": None,
        },
        "price": {"is_free": None, "currency": "CLP", "min_amount": None, "max_amount": None, "display_text": "Consultar condiciones"},
        "links": {"official": None, "tickets": ticket_url, "registration": None, "source": SOURCE_URL},
        "organizer": None,
        "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "source_url": SOURCE_URL, "last_verified_at": verified,
        "public_status": {
            "source_official": False, "last_verified_at": verified, "registration_open": None,
            "registration_closed": None, "cancelled": False, "sold_out": None, "price_stage": None,
            "price_confirmed": False, "information_completeness": "partial",
            "advisory_text": "Confirma horario, precio, disponibilidad y organización en la ficha de venta.",
        },
        "description": "Evento detectado en PortalTickets, utilizado como ticketera y fuente secundaria estructurada.",
        "tags": [category_label, "PortalTickets"], "audience": None, "registration_requirements": None,
        "image": {"url": None, "alt": None},
        "editorial": {"classification": "event", "reason": "secondary_ticketing_source:portaltickets_valparaiso", "duration_days": 0},
    }


def parse_markup(markup: str, today: date | None = None) -> tuple[list[dict], dict]:
    today = today or datetime.now(ZoneInfo(TIMEZONE)).date()
    parser = PortalTokenParser(); parser.feed(markup); parser.close()
    tokens = parser.tokens
    result: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    stats = {"ticket_blocks": 0, "no_date": 0, "expired": 0, "invalid_card": 0, "out_of_scope": 0, "no_individual_ticket": 0, "duplicate_card": 0}
    previous_ticket = -1

    for ticket_index, ticket in enumerate(tokens):
        if not ticket_token(ticket):
            continue
        stats["ticket_blocks"] += 1
        block = tokens[previous_ticket + 1:ticket_index + 1]
        previous_ticket = ticket_index
        dated = [(i, parse_date(str(token.get("text") or ""), today)) for i, token in enumerate(block)]
        dated = [(i, value) for i, value in dated if value]
        if not dated:
            stats["no_date"] += 1; continue
        date_index, (start, clock) = dated[-1]
        if start < today:
            stats["expired"] += 1; continue

        title_candidates = [str(token.get("text") or "").strip() for token in block[:date_index]]
        title = next((candidate for candidate in reversed(title_candidates) if candidate and not bad_title(candidate) and not parse_date(candidate, today)), None)
        venue_candidates = [str(token.get("text") or "").strip() for token in block[date_index + 1:-1]]
        venue = next((candidate for candidate in venue_candidates if looks_like_venue(candidate)), None)
        if not title or not venue or norm(title) == norm(venue):
            if any(out_of_scope(candidate) for candidate in title_candidates + venue_candidates): stats["out_of_scope"] += 1
            else: stats["invalid_card"] += 1
            continue
        if out_of_scope(title) or out_of_scope(venue):
            stats["out_of_scope"] += 1; continue
        city = city_from_venue(venue)
        if not city:
            stats["out_of_scope"] += 1; continue
        ticket_url = individual_ticket_url(ticket)
        if not ticket_url:
            stats["no_individual_ticket"] += 1; continue
        card_key = (norm(title), start.isoformat(), clock, norm(venue))
        if card_key in seen:
            stats["duplicate_card"] += 1; continue
        seen.add(card_key)
        result.append(make_event(title, start, clock, venue, city, ticket_url))
    return result, stats


def fetch_markup() -> tuple[bool, int | None, str, str | None]:
    request = Request(SOURCE_URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310
            raw = response.read(); charset = response.headers.get_content_charset() or "utf-8"
            return True, getattr(response, "status", 200), raw.decode(charset, errors="replace"), None
    except HTTPError as exc:
        return False, exc.code, "", f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, None, "", f"{type(exc).__name__}: {exc}"


def day(item: dict) -> str:
    return str((item.get("schedule") or {}).get("start") or "")[:10]


def item_city(item: dict) -> str:
    return norm((item.get("location") or {}).get("city"))


def semantic_duplicate(candidate: dict, existing: list[dict]) -> bool:
    title = norm(candidate.get("title")); candidate_day = day(candidate); city = item_city(candidate)
    for other in existing:
        if day(other) != candidate_day or item_city(other) != city:
            continue
        other_title = norm(other.get("title"))
        if not other_title:
            continue
        if title == other_title:
            return True
        if title in other_title or other_title in title:
            if min(len(title), len(other_title)) >= 12: return True
        if SequenceMatcher(None, title, other_title).ratio() >= 0.86:
            return True
    return False


def corrected(item: dict) -> bool:
    return str((item.get("editorial") or {}).get("reason") or "") == "secondary_ticketing_source:portaltickets_valparaiso"


def refresh_dataset(dataset: dict, candidates: list[dict], *, fetch_ok: bool) -> tuple[dict, dict]:
    original = list(dataset.get("events") or [])
    base = [item for item in original if str(item.get("source_id") or "") != SOURCE_ID]
    old_portal = [item for item in original if str(item.get("source_id") or "") == SOURCE_ID]
    legacy = [item for item in old_portal if not corrected(item)]
    previous_good = [item for item in old_portal if corrected(item)]

    if not fetch_ok:
        kept_portal = previous_good
        dropped_semantic = 0
    else:
        kept_portal = []
        dropped_semantic = 0
        for candidate in candidates:
            if semantic_duplicate(candidate, base + kept_portal):
                dropped_semantic += 1
                continue
            kept_portal.append(candidate)

    dataset["events"] = sorted(base + kept_portal, key=lambda item: (day(item), str(item.get("title") or "")))
    events = dataset["events"]
    dataset["counts"] = {
        "total": len(events), "events": sum(x.get("event_type") == "event" for x in events),
        "courses": sum(x.get("event_type") == "course" for x in events),
        "flexible_offers": sum(x.get("event_type") == "flexible_offer" for x in events),
        "programs": sum(x.get("event_type") == "program" for x in events),
    }
    return dataset, {
        "legacy_removed": len(legacy), "previous_corrected": len(previous_good), "corrected_published": len(kept_portal),
        "semantic_duplicates_dropped": dropped_semantic,
    }


def report_payload(ok: bool, status: int | None, parse_stats: dict, refresh_stats: dict, candidates: int, error: str | None) -> dict:
    return {
        "schema_version": "1.0.0", "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_id": SOURCE_ID, "source_role": "secondary_ticketing_aggregator", "fetch_ok": ok, "http_status": status,
        "candidates_parsed": candidates, "parse": parse_stats, "refresh": refresh_stats, "error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair and refresh PortalTickets using complete event-card binding.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    ok, status, markup, error = fetch_markup()
    candidates, parse_stats = parse_markup(markup) if ok else ([], {})
    updated, refresh_stats = refresh_dataset(dataset, candidates, fetch_ok=ok)
    report = report_payload(ok, status, parse_stats, refresh_stats, len(candidates), error)
    if args.no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    DATASET.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    QUALITY.parent.mkdir(parents=True, exist_ok=True)
    QUALITY.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
