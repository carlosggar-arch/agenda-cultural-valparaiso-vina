from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
REPORT_PATH = ROOT / "app/data/quality/valpocultura-zero-recovery.json"
AGENDA_URL = "https://valpocultura.cl/agenda-cultural/"
TIMEZONE = "America/Santiago"
SOURCE_ID = "valpocultura"
SOURCE_NAME = "Valpo Cultura"
RECOVERY_REASON = "official_cross_source:valpocultura"

TARGETS = (
    {
        "id": "centex",
        "name": "CENTEX",
        "needle": "centex cartelera",
        "event_type": "program",
        "venue": "CENTEX",
        "address": "Sotomayor 233, Valparaíso",
        "category": ("cultura", "Cultura"),
    },
    {
        "id": "valparaiso_profundo",
        "name": "Valparaíso Profundo",
        "needle": "valparaiso profundo programacion",
        "event_type": "program",
        "venue": "Valparaíso Profundo",
        "address": "Fisher 24, Valparaíso",
        "category": ("cultura", "Cultura"),
    },
    {
        "id": "estrella_negra_jazz",
        "name": "Estrella Negra Club de Jazz",
        "needle": "club de jazz estrella negra cartelera",
        "event_type": "program",
        "venue": "Estrella Negra Club de Jazz",
        "address": "Carrera esquina Chacabuco, Valparaíso",
        "category": ("musica", "Música"),
    },
    {
        "id": "casa_cultura_valparaiso",
        "name": "Casa de la Cultura de Valparaíso",
        "needle": "casa de la cultura de valparaiso",
        "event_type": "event",
        "venue": "Casa de la Cultura de Valparaíso",
        "address": "Cochrane 568, Valparaíso",
        "category": ("musica", "Música"),
    },
    {
        "id": "teatro_municipal_valparaiso",
        "name": "Teatro Municipal de Valparaíso",
        "needle": "teatro municipal cartelera",
        "event_type": "coverage_only",
        "venue": "Teatro Municipal de Valparaíso",
        "address": "Uruguay 410, Valparaíso",
        "category": ("cine", "Cine"),
    },
)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


class AgendaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._href: str | None = None
        self._anchor: list[str] = []
        self.parts: list[str] = []
        self.skip = 0
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs) -> None:
        attrs_map = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "a":
            self._href = attrs_map.get("href")
            self._anchor = []
        if tag == "meta":
            key = attrs_map.get("property") or attrs_map.get("name")
            content = attrs_map.get("content")
            if key and content:
                self.meta[key.casefold()] = content
        if tag in {"br", "p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td"}:
            self.parts.append("\n")

    def handle_endtag(self, tag) -> None:
        if tag in {"script", "style", "noscript"}:
            if self.skip:
                self.skip -= 1
            return
        if self.skip:
            return
        if tag == "a":
            text = re.sub(r"\s+", " ", " ".join(self._anchor)).strip()
            if self._href and text:
                self.links.append({"href": self._href, "text": text})
            self._href = None
            self._anchor = []
        if tag in {"p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td"}:
            self.parts.append("\n")

    def handle_data(self, data) -> None:
        if self.skip:
            return
        self.parts.append(data)
        if self._href is not None and data.strip():
            self._anchor.append(data)

    def lines(self) -> list[str]:
        text = html.unescape("".join(self.parts)).replace("\xa0", " ")
        return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def parse_document(markup: str) -> AgendaParser:
    parser = AgendaParser()
    parser.feed(markup)
    return parser


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
        with urlopen(request, timeout=30) as response:  # nosec B310 - fixed HTTPS source
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


def discover(markup: str) -> list[dict]:
    parser = parse_document(markup)
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for link in parser.links:
        href = urljoin(AGENDA_URL, link["href"])
        if "/evento/" not in href:
            continue
        label = norm(link["text"])
        for target in TARGETS:
            if target["needle"] not in label:
                continue
            key = (target["id"], href)
            if key in seen:
                continue
            seen.add(key)
            found.append({"target": target, "title": link["text"].strip(), "url": href})
    return found


def listing_date_for_href(markup: str, href: str) -> date | None:
    candidates = {href, href.replace("https://valpocultura.cl", "")}
    positions = [markup.find(value) for value in candidates if value and markup.find(value) >= 0]
    if not positions:
        return None
    pos = min(positions)
    before = markup[max(0, pos - 6000):pos]
    dates = re.findall(r"20\d{2}-\d{2}-\d{2}", before)
    for value in reversed(dates):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return None


def jsonld_objects(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from jsonld_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from jsonld_objects(nested)


def extract_jsonld_event(markup: str) -> dict | None:
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        markup,
        flags=re.I | re.S,
    ):
        raw = html.unescape(match.group(1)).strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for obj in jsonld_objects(payload):
            event_type = obj.get("@type")
            types = event_type if isinstance(event_type, list) else [event_type]
            if "Event" in types and obj.get("startDate"):
                return obj
    return None


def as_day(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def visible_dates(markup: str) -> tuple[date | None, date | None]:
    parser = parse_document(markup)
    lines = parser.lines()
    start = end = None
    for line in lines:
        normalized = norm(line)
        matches = re.findall(r"20\d{2}-\d{2}-\d{2}", line)
        if not matches:
            continue
        if normalized.startswith("inicio"):
            start = as_day(matches[0])
        elif normalized.startswith("finaliza"):
            end = as_day(matches[0])
    return start, end


def parse_price(markup: str, jsonld: dict | None) -> dict:
    text = " ".join(parse_document(markup).lines())
    if re.search(r"\bGratuito\b", text, re.I):
        return {"is_free": True, "currency": "CLP", "min_amount": 0, "max_amount": 0, "display_text": "Gratis"}

    # Prefer an explicit visible CLP amount over schema.org offers. Some municipal
    # pages expose "8" in JSON-LD while the human-readable page correctly says
    # "$8.000"; accepting the structured value first would understate the price.
    visible_money = re.search(r"\$\s*([0-9]{1,3}(?:\.[0-9]{3})+|[0-9]{4,})\b", text)
    if visible_money:
        amount_value = int(visible_money.group(1).replace(".", ""))
        return {
            "is_free": False,
            "currency": "CLP",
            "min_amount": amount_value,
            "max_amount": amount_value,
            "display_text": f"${amount_value:,}".replace(",", "."),
        }

    offer = (jsonld or {}).get("offers") or {}
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    raw_price = offer.get("price") if isinstance(offer, dict) else None
    try:
        amount = float(raw_price) if raw_price is not None else None
    except (TypeError, ValueError):
        amount = None
    if amount is not None:
        amount_value = int(amount) if amount.is_integer() else amount
        return {
            "is_free": amount == 0,
            "currency": str(offer.get("priceCurrency") or "CLP"),
            "min_amount": amount_value,
            "max_amount": amount_value,
            "display_text": "Gratis" if amount == 0 else f"${amount_value:,.0f}".replace(",", "."),
        }
    return {"is_free": None, "currency": "CLP", "min_amount": None, "max_amount": None, "display_text": "Consultar condiciones"}


def detail(candidate: dict, listing_markup: str, today: date) -> dict:
    ok, status, markup, error = fetch(candidate["url"])
    target = candidate["target"]
    jsonld = extract_jsonld_event(markup) if ok else None
    start = as_day((jsonld or {}).get("startDate"))
    end = as_day((jsonld or {}).get("endDate"))
    if ok and not start:
        visible_start, visible_end = visible_dates(markup)
        start = visible_start
        end = end or visible_end
    start = start or listing_date_for_href(listing_markup, candidate["url"])
    title = str((jsonld or {}).get("name") or candidate["title"]).strip()
    image = (jsonld or {}).get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")
    if not image and ok:
        image = parse_document(markup).meta.get("og:image")
    price = parse_price(markup, jsonld) if ok else {
        "is_free": None, "currency": "CLP", "min_amount": None, "max_amount": None, "display_text": "Consultar condiciones"
    }
    active = bool(start and (end or start) >= today)
    publishable = active and target["event_type"] != "coverage_only"
    if target["event_type"] == "program" and not end:
        publishable = False
    return {
        "target": target,
        "title": title,
        "url": candidate["url"],
        "fetch_ok": ok,
        "http_status": status,
        "error": error,
        "start": start,
        "end": end,
        "active": active,
        "publishable": publishable,
        "price": price,
        "image": str(image).strip() if image else None,
    }


def event_key(item: dict) -> tuple[str, str, str]:
    return (
        norm(item.get("title")),
        str((item.get("schedule") or {}).get("start") or "")[:10],
        norm((item.get("location") or {}).get("city")),
    )


def make_event(row: dict) -> dict:
    target = row["target"]
    start: date = row["start"]
    end: date = row["end"] or start
    event_type = target["event_type"]
    verified = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    digest = hashlib.sha1(f"{SOURCE_ID}|{target['id']}|{start}|{row['title']}".encode()).hexdigest()[:16]
    category_id, category_label = target["category"]
    image = {"url": row["image"], "alt": row["title"] if row["image"] else None}
    if row["image"]:
        image["source"] = "official_municipal_cross_source"
        image["relevance"] = "generic_schedule" if event_type == "program" else "event_specific"
    return {
        "id": f"agenda_valpocultura_recovery_{digest}",
        "title": row["title"],
        "event_type": event_type,
        "primary_category": {"id": category_id, "label": category_label},
        "categories": [{"id": category_id, "label": category_label}],
        "schedule": {
            "mode": "multi_day" if end != start else "single",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": TIMEZONE,
            "display_text": f"{start.isoformat()} – {end.isoformat()}" if end != start else start.isoformat(),
            "occurrences": [],
            "start_confidence": "explicit",
            "end_confidence": "explicit" if row["end"] else "same_day_default",
        },
        "location": {
            "venue_id": target["id"],
            "city": "Valparaíso",
            "commune": "Valparaíso",
            "venue": target["venue"],
            "address": target["address"],
            "online": False,
            "latitude": None,
            "longitude": None,
        },
        "price": row["price"],
        "links": {"official": row["url"], "tickets": None, "registration": None, "source": row["url"]},
        "organizer": target["name"],
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": row["url"],
        "last_verified_at": verified,
        "public_status": {
            "source_official": True,
            "last_verified_at": verified,
            "registration_open": None,
            "registration_closed": None,
            "cancelled": False,
            "sold_out": None,
            "price_stage": None,
            "price_confirmed": row["price"]["is_free"] is not None,
            "information_completeness": "complete" if row["end"] or event_type == "event" else "partial",
            "advisory_text": "Fuente secundaria oficial municipal; confirma condiciones en la ficha enlazada.",
        },
        "description": f"Cobertura municipal oficial de programación de {target['name']}.",
        "tags": [category_label, target["name"], SOURCE_NAME],
        "audience": None,
        "registration_requirements": None,
        "image": image,
        "editorial": {
            "classification": "program" if event_type == "program" else "event",
            "reason": RECOVERY_REASON,
            "covered_source_ids": [target["id"]],
            "duration_days": max(0, (end - start).days),
        },
    }


def refresh_dataset(dataset: dict, rows: list[dict], fetch_ok: bool) -> tuple[dict, dict]:
    events = list(dataset.get("events") or [])
    previous = [
        item for item in events
        if str((item.get("editorial") or {}).get("reason") or "") == RECOVERY_REASON
    ]
    base = [item for item in events if item not in previous]
    if not fetch_ok:
        return dataset, {"previous_recovery": len(previous), "published": len(previous), "preserved_previous": True, "duplicates_skipped": 0}
    known = {event_key(item) for item in base}
    additions = []
    duplicates = 0
    for row in rows:
        if not row["publishable"]:
            continue
        item = make_event(row)
        if event_key(item) in known:
            duplicates += 1
            continue
        known.add(event_key(item))
        additions.append(item)
    dataset["events"] = sorted(
        base + additions,
        key=lambda item: (str((item.get("schedule") or {}).get("start") or ""), str(item.get("title") or "")),
    )
    all_events = dataset["events"]
    dataset["counts"] = {
        "total": len(all_events),
        "events": sum(item.get("event_type") == "event" for item in all_events),
        "courses": sum(item.get("event_type") == "course" for item in all_events),
        "flexible_offers": sum(item.get("event_type") == "flexible_offer" for item in all_events),
        "programs": sum(item.get("event_type") == "program" for item in all_events),
    }
    return dataset, {
        "previous_recovery": len(previous),
        "published": len(additions),
        "preserved_previous": False,
        "duplicates_skipped": duplicates,
    }


def prior_report() -> dict:
    if not REPORT_PATH.exists():
        return {}
    try:
        return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build(no_write: bool = False) -> tuple[dict, dict]:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    ok, status, markup, error = fetch(AGENDA_URL)
    if not ok:
        previous = prior_report()
        report = {
            "schema_version": "1.0.0",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": AGENDA_URL,
            "fetch_ok": False,
            "http_status": status,
            "error": error,
            "state": "fetch_error_preserving_previous",
            "coverage": previous.get("coverage") or [],
            "refresh": {"preserved_previous": True},
        }
        return dataset, report

    discovered = discover(markup)
    rows = [detail(candidate, markup, today) for candidate in discovered]
    dataset, refresh = refresh_dataset(dataset, rows, fetch_ok=True)
    coverage = []
    dataset_keys = {event_key(item) for item in dataset.get("events") or []}
    for row in rows:
        if not row["active"]:
            continue
        coverage.append({
            "source_id": row["target"]["id"],
            "source_name": row["target"]["name"],
            "covered_by": SOURCE_ID,
            "title": row["title"],
            "url": row["url"],
            "start": row["start"].isoformat() if row["start"] else None,
            "end": row["end"].isoformat() if row["end"] else None,
            "publishable": row["publishable"],
            "published": row["publishable"] and event_key(make_event(row)) in dataset_keys,
            "detail_fetch_ok": row["fetch_ok"],
        })
    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": AGENDA_URL,
        "fetch_ok": True,
        "http_status": status,
        "error": None,
        "state": "ok",
        "discovered": len(discovered),
        "active_coverage": len(coverage),
        "coverage": coverage,
        "refresh": refresh,
    }
    return dataset, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover high-value Valparaiso coverage from the official municipal cultural agenda.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    dataset, report = build(no_write=args.no_write)
    if args.no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    DATASET_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
