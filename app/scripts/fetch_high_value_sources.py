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
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "app/data/high_value_sources.json"
QUALITY = ROOT / "app/data/quality/high-value-sources.json"
DATASETS = {
    "valparaiso": ROOT / "agenda_web.json",
    "gijon": ROOT / "app/data/gijon/agenda_web.json",
}
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MONTH_PATTERN = "|".join(MONTHS)


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        elif tag in {"br", "p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td"}:
            self.parts.append("\n")

    def handle_endtag(self, tag) -> None:
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1
        elif tag in {"p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "tr", "td"}:
            self.parts.append("\n")

    def handle_data(self, data) -> None:
        if not self.skip:
            self.parts.append(data)

    def lines(self) -> list[str]:
        text = html.unescape("".join(self.parts)).replace("\xa0", " ")
        return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def fetch(url: str) -> tuple[bool, int | None, str, str | None]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310 - configured HTTPS sources
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


def lines(markup: str) -> list[str]:
    parser = TextParser()
    parser.feed(markup)
    return parser.lines()


def now_day(source: dict) -> date:
    return datetime.now(ZoneInfo(source["timezone"])).date()


def iso(day: date, clock: str | None, timezone: str) -> str:
    if not clock:
        return day.isoformat()
    return datetime.fromisoformat(f"{day.isoformat()}T{clock}:00").replace(tzinfo=ZoneInfo(timezone)).isoformat(timespec="seconds")


def event(source: dict, title: str, start: date, *, end: date | None = None, clock: str | None = None,
          city: str | None = None, venue: str | None = None, address: str | None = None) -> dict:
    end = end or start
    city = city or source["city"]
    verified = datetime.now(ZoneInfo(source["timezone"])).isoformat(timespec="seconds")
    digest = hashlib.sha1(f"{source['id']}|{start}|{title}|{city}".encode()).hexdigest()[:16]
    category_id = source["category_id"]
    category_label = source["category_label"]
    return {
        "id": f"agenda_{source['id']}_{digest}",
        "title": title.strip(),
        "event_type": "event",
        "primary_category": {"id": category_id, "label": category_label},
        "categories": [{"id": category_id, "label": category_label}],
        "schedule": {
            "mode": "multi_day" if end != start else "single",
            "start": iso(start, clock, source["timezone"]),
            "end": iso(end, None if end != start else clock, source["timezone"]),
            "timezone": source["timezone"],
            "display_text": f"{start} – {end}" if end != start else f"{start}{' · ' + clock if clock else ''}",
            "occurrences": [], "start_confidence": "explicit", "end_confidence": "explicit",
        },
        "location": {
            "venue_id": source["id"], "city": city, "commune": city,
            "venue": venue or source["name"], "address": address, "online": False,
            "latitude": None, "longitude": None,
        },
        "price": {"is_free": None, "currency": source["currency"], "min_amount": None, "max_amount": None, "display_text": "Consultar condiciones"},
        "links": {"official": source["url"], "tickets": None, "registration": None, "source": source["url"]},
        "organizer": source["name"], "source_id": source["id"], "source_name": source["name"], "source_url": source["url"],
        "last_verified_at": verified,
        "public_status": {
            "source_official": True, "last_verified_at": verified, "registration_open": None,
            "registration_closed": None, "cancelled": False, "sold_out": None, "price_stage": None,
            "price_confirmed": False, "information_completeness": "partial",
            "advisory_text": "Confirma horario, precio y condiciones en la fuente oficial.",
        },
        "description": f"Actividad publicada por {source['name']}.",
        "tags": [category_label, source["name"]], "audience": None, "registration_requirements": None,
        "image": {"url": None, "alt": None},
        "editorial": {"classification": "event", "reason": f"high_value_source:{source['id']}", "duration_days": max(0, (end - start).days)},
    }


def parse_date_es(day: str, month: str, year: str) -> date | None:
    month_number = MONTHS.get(slug(month))
    try:
        return date(int(year), month_number, int(day)) if month_number else None
    except ValueError:
        return None


def extract_barjola(source: dict, text: list[str]) -> list[dict]:
    result = []
    pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})$")
    today = now_day(source)
    for index, value in enumerate(text[:-1]):
        match = pattern.match(value)
        if not match:
            continue
        try:
            start = datetime.strptime(match.group(1), "%d/%m/%Y").date()
            end = datetime.strptime(match.group(2), "%d/%m/%Y").date()
        except ValueError:
            continue
        if end < today:
            continue
        title = text[index + 1]
        if slug(title) in {"buscador", "ano", "ver"}:
            continue
        result.append(event(source, title, start, end=end, city="Gijón", venue="Museo Barjola", address="C/ Trinidad, 17, Gijón"))
    return result


LABORAL_ITEM = re.compile(
    rf"^(\d{{1,2}})\s+de\s+({MONTH_PATTERN})\.?\s*(?:(20\d{{2}})[,.]?\s*)?(\d{{1,2}}):(\d{{2}})\s*h\.?\s*(.+)$",
    re.I,
)
GENERIC = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})(?:.{0,20}?(\d{1,2})[:.](\d{2}))?")


def extract_laboral(source: dict, text: list[str]) -> list[dict]:
    """Extract only explicit Laboral Cinemateca programme lines from a trusted Asturias agenda page."""
    normalized_page = " ".join(slug(value) for value in text)
    if "laboral cinemateca" not in normalized_page or "gijon" not in normalized_page:
        return []
    result = []
    today = now_day(source)
    seen = set()
    for value in text:
        match = LABORAL_ITEM.match(value)
        if not match:
            continue
        year = match.group(3) or str(today.year)
        start = parse_date_es(match.group(1), match.group(2), year)
        if not start or start < today:
            continue
        title = re.sub(r"^(?:Estaciones|Infantil y juvenil|Programas especiales|Muestra Asturies|BS\(O\) en vivo)\.\s*", "", match.group(6), flags=re.I).strip(" .")
        if len(title) < 4:
            continue
        clock = f"{int(match.group(4)):02d}:{match.group(5)}"
        signature = (start.isoformat(), clock, slug(title))
        if signature in seen:
            continue
        seen.add(signature)
        result.append(event(source, title, start, clock=clock, city="Gijón", venue="Laboral Ciudad de la Cultura"))
    return result


def extract_generic(source: dict, text: list[str]) -> list[dict]:
    result = []
    today = now_day(source)
    for index, value in enumerate(text):
        match = GENERIC.search(value)
        if not match:
            continue
        try:
            start = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            continue
        if start < today:
            continue
        title = text[index - 1] if index else ""
        if len(title) < 6 or slug(title) in {"agenda", "actualidad", "programacion"}:
            continue
        clock = f"{int(match.group(4)):02d}:{match.group(5)}" if match.group(4) else None
        result.append(event(source, title, start, clock=clock))
    return result


EXTRACTORS = {
    "barjola_exhibitions": extract_barjola,
    "laboral_program": extract_laboral,
    "generic_dated": extract_generic,
}


def key(item: dict) -> tuple[str, str, str]:
    return (slug(str(item.get("title") or "")), str((item.get("schedule") or {}).get("start") or "")[:10], slug(str((item.get("location") or {}).get("city") or "")))


def merge(dataset: dict, additions: list[dict]) -> tuple[int, int]:
    known = {key(item) for item in dataset.get("events", [])}
    added = duplicates = 0
    for item in additions:
        if key(item) in known:
            duplicates += 1
            continue
        dataset.setdefault("events", []).append(item)
        known.add(key(item))
        added += 1
    dataset["events"].sort(key=lambda item: (str((item.get("schedule") or {}).get("start") or ""), str(item.get("title") or "")))
    all_events = dataset["events"]
    dataset["counts"] = {
        "total": len(all_events), "events": sum(x.get("event_type") == "event" for x in all_events),
        "courses": sum(x.get("event_type") == "course" for x in all_events),
        "flexible_offers": sum(x.get("event_type") == "flexible_offer" for x in all_events),
        "programs": sum(x.get("event_type") == "program" for x in all_events),
    }
    return added, duplicates


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(no_write: bool = False, only: set[str] | None = None) -> int:
    sources = load(CONFIG)["sources"]
    datasets = {name: load(path) for name, path in DATASETS.items()}
    staged: dict[str, list[tuple[str, dict]]] = {"valparaiso": [], "gijon": []}
    report = {"schema_version": "1.0.0", "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"), "sources": []}

    for source in sources:
        if only and source["id"] not in only:
            continue
        ok, status_code, markup, error = fetch(source["url"])
        status = {
            "id": source["id"], "name": source["name"], "dataset": source["dataset"], "mode": source["mode"],
            "fetch_ok": ok, "http_status": status_code, "events_extracted": 0, "events_added": 0,
            "duplicates_skipped": 0, "state": "ok" if ok else "fetch_error", "error": error,
        }
        if ok:
            extractor = EXTRACTORS.get(source["extractor"])
            if extractor is None:
                raise ValueError(f"Unknown high-value extractor: {source['extractor']}")
            candidates = extractor(source, lines(markup))
            if source["dataset"] == "valparaiso":
                candidates = [item for item in candidates if item["location"]["city"] in {"Valparaíso", "Viña del Mar"}]
            else:
                candidates = [item for item in candidates if item["location"]["city"] == "Gijón"]
            status["events_extracted"] = len(candidates)
            if source["mode"] == "monitor" and not candidates:
                status["state"] = "monitored_no_publishable_events"
            staged[source["dataset"]].extend((source["id"], item) for item in candidates)
        report["sources"].append(status)

    for dataset_name, pairs in staged.items():
        grouped: dict[str, list[dict]] = {}
        for source_id, item in pairs:
            grouped.setdefault(source_id, []).append(item)
        for source_id, items in grouped.items():
            added, duplicates = merge(datasets[dataset_name], items)
            status = next(row for row in report["sources"] if row["id"] == source_id)
            status["events_added"] = added
            status["duplicates_skipped"] = duplicates

    if no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for name, path in DATASETS.items():
            save(path, datasets[name])
        save(QUALITY, report)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and merge the high-value supplemental sources.")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args()
    raise SystemExit(run(args.no_write, set(args.only) or None))


if __name__ == "__main__":
    main()
