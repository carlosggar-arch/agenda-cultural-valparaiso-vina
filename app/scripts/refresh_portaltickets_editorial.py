from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
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
DETAIL_MAX_WORKERS = 8
DETAIL_TIMEOUT = 15
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
PRICE_AMOUNT = re.compile(r"\$\s*([0-9][0-9.]*)")
STOPWORDS = {"en", "el", "la", "los", "las", "de", "del", "y", "a"}
VENUE_WORDS = {
    "teatro", "bar", "cafe", "club", "espacio", "parque", "sala", "centro", "journal", "pasaje",
    "patio", "cassot", "lemutt", "trotamundos", "balmaceda", "universidad",
}
DESCRIPTION_BOILERPLATE = (
    "este concierto forma parte", "el teatro mauri scd es", "el teatro mauri scd", "construido entre",
    "datos practicos", "hora de apertura", "hora aprox", "como llegar", "dentro del teatro", "siguenos",
    "evento para todas las edades", "politicas de reembolso", "te invitamos a conocer las politicas",
)
DESCRIPTION_HEADINGS = {
    "fecha", "lugar", "produce", "descripcion", "tickets disponibles", "todos los eventos", "ver mapa",
    "grupo region", "artistas y tags relacionados", "politicas de reembolso", "contacto", "links relacionados",
}


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
    value = f" {norm(title)} "
    if any(term in value for term in (" pelicula ", " documental ", " cortometraje ", " largometraje ")):
        return "cine", "Cine"
    if any(term in value for term in (
        " obra de teatro ", " obra teatral ", " stand up ", " monologo ", " comedia teatral ", " dramaturgia ",
    )):
        return "teatro", "Teatro"
    if any(term in value for term in (
        " concierto ", " orquesta ", " ensamble ", " trio ", " banda ", " tributo ", " gira ", " tour ", " tocata ",
        " dj ", " vinilo ", " sonora ", " sinfonico ", " lanzamiento disco ", " quinteto ", " cuarteto ",
        " canciones ", " musica ", " musical ", " cantante ", " cantautor ",
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
        "price": {"is_free": None, "currency": "CLP", "min_amount": None, "max_amount": None, "display_text": None},
        "links": {"official": None, "tickets": ticket_url, "registration": None, "source": ticket_url},
        "organizer": None,
        "source_id": SOURCE_ID, "source_name": SOURCE_NAME, "source_url": ticket_url, "last_verified_at": verified,
        "public_status": {
            "source_official": False, "last_verified_at": verified, "registration_open": None,
            "registration_closed": None, "cancelled": False, "sold_out": None, "price_stage": None,
            "price_confirmed": False, "information_completeness": "partial",
            "advisory_text": "Confirma disponibilidad y condiciones en la ficha de venta.",
        },
        "description": None,
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


def fetch_url(url: str, timeout: int = DETAIL_TIMEOUT) -> tuple[bool, int | None, str, str | None]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            raw = response.read(); charset = response.headers.get_content_charset() or "utf-8"
            return True, getattr(response, "status", 200), raw.decode(charset, errors="replace"), None
    except HTTPError as exc:
        return False, exc.code, "", f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, None, "", f"{type(exc).__name__}: {exc}"


def fetch_markup() -> tuple[bool, int | None, str, str | None]:
    return fetch_url(SOURCE_URL, timeout=30)


def _meaningful_tokens(value: object) -> list[str]:
    return [word for word in norm(value).split() if word not in STOPWORDS]


def _redundant_venue_suffix(suffix: str, venue: str, city: str) -> bool:
    suffix_tokens = _meaningful_tokens(suffix)
    if len(suffix_tokens) < 2:
        return False
    venue_tokens = set(_meaningful_tokens(f"{venue} {city}"))
    if not venue_tokens:
        return False
    overlap = sum(word in venue_tokens for word in suffix_tokens) / len(suffix_tokens)
    return overlap >= 0.8 and (bool(set(suffix_tokens) & VENUE_WORDS) or len(suffix_tokens) >= 3)


def clean_public_title(title: str, venue: str, city: str) -> str:
    value = re.sub(r"\s+", " ", str(title or "")).strip()
    matches = list(re.finditer(r"\s+en\s+", value, flags=re.I))
    if not matches:
        return value
    match = matches[-1]
    suffix = value[match.end():].strip(" ,.;:–—-")
    if not _redundant_venue_suffix(suffix, venue, city):
        return value
    cleaned = value[:match.start()].strip(" ,.;:–—-")
    return cleaned or value


def _parse_amount(value: str) -> int | None:
    digits = re.sub(r"\D", "", value or "")
    return int(digits) if digits else None


def _format_clp(value: int) -> str:
    return "$" + f"{value:,}".replace(",", ".")


def _description_from_tokens(texts: list[str]) -> str | None:
    description_index = next((i for i, text in enumerate(texts) if norm(text) == "descripcion"), None)
    if description_index is None:
        return None
    selected: list[str] = []
    for text in texts[description_index + 1:]:
        cleaned = re.sub(r"\s+", " ", text).strip()
        normalized = norm(cleaned)
        if not cleaned:
            continue
        if normalized in DESCRIPTION_HEADINGS:
            if selected:
                break
            continue
        if any(normalized.startswith(prefix) for prefix in DESCRIPTION_BOILERPLATE):
            if selected:
                break
            continue
        if len(cleaned) < 25:
            continue
        selected.append(cleaned)
        if len(" ".join(selected)) >= 420 or len(selected) >= 2:
            break
    if not selected:
        return None
    value = " ".join(selected)
    return value[:520].rstrip(" ,;:")


def parse_detail_markup(markup: str) -> dict:
    parser = PortalTokenParser(); parser.feed(markup); parser.close()
    texts = [str(token.get("text") or "").strip() for token in parser.tokens if str(token.get("text") or "").strip()]
    description = _description_from_tokens(texts)
    tiers: list[dict] = []
    amounts: list[int] = []
    for index, text in enumerate(texts):
        found = [_parse_amount(match) for match in PRICE_AMOUNT.findall(text)]
        found = [value for value in found if value is not None]
        if not found:
            continue
        window = norm(" ".join(texts[index:index + 3]))
        sold = bool(re.search(r"\bagotad[oa]s?\b", window))
        last = "ultimos tickets" in window
        buy = "comprar" in window or "regalar" in window
        tiers.append({"amounts": found, "sold": sold, "last": last, "buy": buy})
        amounts.extend(found)

    explicit_sold = any("evento agotado" in norm(text) or norm(text) == "agotado" for text in texts)
    all_tiers_sold = bool(tiers) and all(tier["sold"] and not tier["buy"] and not tier["last"] for tier in tiers)
    sold_out = explicit_sold or all_tiers_sold
    any_sold = any(tier["sold"] for tier in tiers)
    any_available = any(tier["buy"] or tier["last"] or not tier["sold"] for tier in tiers)
    last_tickets = any(tier["last"] for tier in tiers)
    partial = any_sold and any_available and not sold_out

    price_min = min(amounts) if amounts else None
    price_max = max(amounts) if amounts else None
    if sold_out:
        price_text = "Entradas agotadas"
    elif price_min is not None:
        price_text = _format_clp(price_min) if price_min == price_max else f"{_format_clp(price_min)}–{_format_clp(price_max)}"
        if last_tickets:
            price_text += " · Últimos tickets"
        elif partial:
            price_text += " · Algunos sectores agotados"
    else:
        price_text = None

    return {
        "description": description,
        "sold_out": sold_out if (tiers or explicit_sold) else None,
        "registration_open": False if sold_out else (True if tiers and any_available else None),
        "price_stage": "Últimos tickets" if last_tickets else ("Disponibilidad parcial" if partial else None),
        "price_min": price_min,
        "price_max": price_max,
        "price_text": price_text,
        "price_confirmed": bool(amounts),
        "partial_availability": partial,
        "last_tickets": last_tickets,
    }


def apply_detail(event: dict, detail: dict, *, verified_at: str) -> dict:
    location = event.get("location") or {}
    old_title = str(event.get("title") or "").strip()
    new_title = clean_public_title(old_title, str(location.get("venue") or ""), str(location.get("city") or ""))
    if new_title != old_title:
        event["title"] = new_title
        editorial = event.setdefault("editorial", {})
        editorial["source_title_original"] = old_title
        editorial["venue_suffix_removed"] = True

    description = detail.get("description")
    event["description"] = description or None

    price = event.setdefault("price", {})
    if detail.get("price_min") is not None:
        price["is_free"] = False
        price["currency"] = "CLP"
        price["min_amount"] = detail.get("price_min")
        price["max_amount"] = detail.get("price_max")
        price["display_text"] = detail.get("price_text")
    elif detail.get("sold_out") is True:
        price["is_free"] = False
        price["currency"] = "CLP"
        price["display_text"] = "Entradas agotadas"
    else:
        price["display_text"] = None

    status = event.setdefault("public_status", {})
    status["last_verified_at"] = verified_at
    status["sold_out"] = detail.get("sold_out")
    status["registration_open"] = detail.get("registration_open")
    status["price_stage"] = detail.get("price_stage")
    status["price_confirmed"] = bool(detail.get("price_confirmed"))
    status["information_completeness"] = "complete"
    status["advisory_text"] = None
    event["last_verified_at"] = verified_at

    combined = f"{event.get('title') or ''} {description or ''}"
    category_id, category_label = category_for(combined)
    if category_id != "cultura" or (event.get("primary_category") or {}).get("id") == "cultura":
        event["primary_category"] = {"id": category_id, "label": category_label}
        event["categories"] = [{"id": category_id, "label": category_label}]
        tags = [tag for tag in (event.get("tags") or []) if norm(tag) not in {"cultura", "musica", "teatro", "cine"}]
        event["tags"] = [category_label, *tags]

    editorial = event.setdefault("editorial", {})
    editorial["detail_enriched"] = True
    editorial["detail_verified_at"] = verified_at
    if detail.get("partial_availability"):
        editorial["partial_ticket_availability"] = True
    if detail.get("last_tickets"):
        editorial["last_tickets"] = True
    return event


def enrich_candidates(candidates: list[dict]) -> tuple[list[dict], dict]:
    stats = {
        "requested": len(candidates), "fetched": 0, "failed": 0, "titles_shortened": 0,
        "descriptions_added": 0, "descriptions_missing": 0, "sold_out": 0,
        "partial_availability": 0, "last_tickets": 0, "prices_confirmed": 0,
    }
    if not candidates:
        return candidates, stats

    results: dict[str, tuple[bool, int | None, str, str | None]] = {}
    with ThreadPoolExecutor(max_workers=DETAIL_MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_url, str((event.get("links") or {}).get("tickets") or "")): str(event.get("id") or "")
            for event in candidates
            if (event.get("links") or {}).get("tickets")
        }
        for future in as_completed(futures):
            event_id = futures[future]
            try:
                results[event_id] = future.result()
            except Exception as exc:  # pragma: no cover - defensive isolation around remote pages
                results[event_id] = (False, None, "", f"{type(exc).__name__}: {exc}")

    enriched: list[dict] = []
    verified_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    for event in candidates:
        old_title = str(event.get("title") or "")
        location = event.get("location") or {}
        cleaned_title = clean_public_title(old_title, str(location.get("venue") or ""), str(location.get("city") or ""))
        response = results.get(str(event.get("id") or ""))
        if not response or not response[0]:
            if cleaned_title != old_title:
                event["title"] = cleaned_title
                event.setdefault("editorial", {})["source_title_original"] = old_title
                event["editorial"]["venue_suffix_removed"] = True
                stats["titles_shortened"] += 1
            event["description"] = None
            stats["failed"] += 1
            enriched.append(event)
            continue

        stats["fetched"] += 1
        detail = parse_detail_markup(response[2])
        apply_detail(event, detail, verified_at=verified_at)
        if cleaned_title != old_title:
            stats["titles_shortened"] += 1
        if event.get("description"):
            stats["descriptions_added"] += 1
        else:
            stats["descriptions_missing"] += 1
        if detail.get("sold_out") is True:
            stats["sold_out"] += 1
        if detail.get("partial_availability"):
            stats["partial_availability"] += 1
        if detail.get("last_tickets"):
            stats["last_tickets"] += 1
        if detail.get("price_confirmed"):
            stats["prices_confirmed"] += 1
        enriched.append(event)
    return enriched, stats


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


def event_identity(item: dict) -> tuple[str, str, str, str]:
    location = item.get("location") or {}
    schedule = item.get("schedule") or {}
    return (norm(item.get("title")), str(schedule.get("start") or ""), norm(location.get("city")), norm(location.get("venue")))


def stable_event(item: dict) -> dict:
    clone = json.loads(json.dumps(item, ensure_ascii=False))
    clone.pop("last_verified_at", None)
    if isinstance(clone.get("public_status"), dict):
        clone["public_status"].pop("last_verified_at", None)
    if isinstance(clone.get("editorial"), dict):
        clone["editorial"].pop("detail_verified_at", None)
    return clone


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
        previous_by_identity = {event_identity(item): item for item in previous_good}
        for candidate in candidates:
            if semantic_duplicate(candidate, base + kept_portal):
                dropped_semantic += 1
                continue
            previous = previous_by_identity.get(event_identity(candidate))
            if previous is not None and stable_event(previous) == stable_event(candidate):
                kept_portal.append(previous)
            else:
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


def report_payload(
    ok: bool,
    status: int | None,
    parse_stats: dict,
    refresh_stats: dict,
    detail_stats: dict,
    candidates: int,
    error: str | None,
) -> dict:
    return {
        "schema_version": "1.1.0", "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_id": SOURCE_ID, "source_role": "secondary_ticketing_aggregator", "fetch_ok": ok, "http_status": status,
        "candidates_parsed": candidates, "parse": parse_stats, "details": detail_stats, "refresh": refresh_stats, "error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair, enrich and refresh PortalTickets using complete event-card binding.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    ok, status, markup, error = fetch_markup()
    candidates, parse_stats = parse_markup(markup) if ok else ([], {})
    if ok and not args.no_write:
        candidates, detail_stats = enrich_candidates(candidates)
    else:
        detail_stats = {"skipped": "no_write" if args.no_write else "catalog_fetch_failed", "requested": len(candidates)}
    updated, refresh_stats = refresh_dataset(dataset, candidates, fetch_ok=ok)
    report = report_payload(ok, status, parse_stats, refresh_stats, detail_stats, len(candidates), error)
    if args.no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    DATASET.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    QUALITY.parent.mkdir(parents=True, exist_ok=True)
    QUALITY.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
