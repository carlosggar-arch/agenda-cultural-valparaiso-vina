from __future__ import annotations

import argparse
import json
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from update_gijon import build_dataset

SOURCE_URL = "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML"
MOJIBAKE_MARKERS = ("Ã", "Â", "â", "ð", "�", "\x81", "\x8d", "\x8f", "\x90", "\x9d")
CP1252_BYTES = {
    "€": 0x80, "‚": 0x82, "ƒ": 0x83, "„": 0x84, "…": 0x85,
    "†": 0x86, "‡": 0x87, "ˆ": 0x88, "‰": 0x89, "Š": 0x8A,
    "‹": 0x8B, "Œ": 0x8C, "Ž": 0x8E, "‘": 0x91, "’": 0x92,
    "“": 0x93, "”": 0x94, "•": 0x95, "–": 0x96, "—": 0x97,
    "˜": 0x98, "™": 0x99, "š": 0x9A, "›": 0x9B, "œ": 0x9C,
    "ž": 0x9E, "Ÿ": 0x9F,
}
GENERIC_VENUES = {"", "gijón/xixón", "gijón", "xixón"}
FLEXIBLE_TITLE_MARKERS = (
    "visita comentada",
    "visitas comentadas",
    "visita guiada",
    "visitas guiadas",
    "conoce el muséu",
    "conoce el museo",
    "recorrido",
    "recorridos",
)
PROGRAM_MARKERS = (
    "super evento (programa)",
    "programa",
    "programación",
    "ciclo",
    "temporada",
    "compañías",
    "escena xixón",
    "escena amateur",
)


def legacy_bytes(value: str) -> bytes:
    data = bytearray()
    for character in value:
        if character in CP1252_BYTES:
            data.append(CP1252_BYTES[character])
        elif ord(character) <= 0xFF:
            data.append(ord(character))
        else:
            raise UnicodeEncodeError("legacy", character, 0, 1, "not representable")
    return bytes(data)


def repair_mojibake(value: str) -> str:
    """Repair local UTF-8 sequences exposed through mixed Latin-1/Windows-1252 decoding."""
    current = value
    for _ in range(3):
        if not any(marker in current for marker in MOJIBAKE_MARKERS):
            break
        output: list[str] = []
        index = 0
        changed = False
        while index < len(current):
            replacement = None
            consumed = 0
            for length in (4, 3, 2):
                chunk = current[index:index + length]
                if len(chunk) < 2:
                    continue
                try:
                    decoded = legacy_bytes(chunk).decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue
                if decoded != chunk:
                    replacement = decoded
                    consumed = length
                    break
            if replacement is not None:
                output.append(replacement)
                index += consumed
                changed = True
            else:
                output.append(current[index])
                index += 1
        repaired = "".join(output)
        if not changed or repaired == current:
            break
        current = repaired
    return current


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.current_row: list[str] | None = None
        self.current_cell: list[str] | None = None
        self.cell_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.current_row = []
        elif tag in {"th", "td"} and self.current_row is not None:
            self.current_cell = []
            self.cell_href = None
        elif tag == "a" and self.current_cell is not None:
            self.cell_href = dict(attrs).get("href")

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None:
            self.current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self.current_cell is not None and self.current_row is not None:
            text = repair_mojibake(" ".join("".join(self.current_cell).split()))
            if self.cell_href:
                text = f'<a href="{self.cell_href}">{text}</a>'
            self.current_row.append(text)
            self.current_cell = None
            self.cell_href = None
        elif tag == "tr" and self.current_row is not None:
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = None


def fetch_rows(url: str = SOURCE_URL) -> list[dict]:
    request = Request(url, headers={"Accept": "text/html,application/xhtml+xml", "User-Agent": "AgendaCultural/1.0"})
    with urlopen(request, timeout=30) as response:  # nosec B310 - fixed official URL
        text = response.read().decode("utf-8", errors="replace")

    parser = TableParser()
    parser.feed(text)
    if len(parser.rows) < 2:
        raise ValueError("La tabla XHTML de Gijón no contiene filas de datos")

    headers = parser.rows[0]
    if "titulo" not in headers or "materia" not in headers or "fechas" not in headers:
        raise ValueError(f"Cabeceras inesperadas en Open Data Gijón: {headers[:8]}")

    items: list[dict] = []
    for row in parser.rows[1:]:
        if len(row) != len(headers):
            continue
        item = dict(zip(headers, row))
        for key, value in list(item.items()):
            if key == "field_boton_asistencia_registro_":
                continue
            if value.startswith('<a href="'):
                item[key] = value.split('"', 2)[1]
        items.append(item)
    if not items:
        raise ValueError("No se pudieron extraer eventos de la tabla XHTML de Gijón")
    return items


def event_dates(event: dict) -> tuple[date | None, date | None]:
    schedule = event.get("schedule") or {}
    try:
        start = date.fromisoformat(str(schedule.get("start") or "")[:10])
    except ValueError:
        start = None
    try:
        end = date.fromisoformat(str(schedule.get("end") or schedule.get("start") or "")[:10])
    except ValueError:
        end = start
    return start, end


def duration_days(event: dict) -> int:
    start, end = event_dates(event)
    if not start or not end:
        return 0
    return max(0, (end - start).days)


def editorial_text(event: dict) -> str:
    values = [
        event.get("title"),
        event.get("description"),
        event.get("primary_category", {}).get("label"),
        event.get("location", {}).get("venue"),
        *(event.get("tags") or []),
    ]
    return " ".join(str(value or "") for value in values).casefold()


def classify_editorial(event: dict) -> tuple[str, str]:
    """Separate concrete events, umbrella programs and genuinely reusable long-running offers."""
    days = duration_days(event)
    text = editorial_text(event)
    title_text = str(event.get("title") or "").casefold()
    venue = str(event.get("location", {}).get("venue") or "").strip().casefold()
    category_id = str(event.get("primary_category", {}).get("id") or "")

    if event.get("event_type") == "program" or "super evento (programa)" in text:
        return "program", "explicit_program"

    if days >= 90 and venue in GENERIC_VENUES:
        return "program", "long_running_generic_program"

    if days >= 365 and any(marker in text for marker in PROGRAM_MARKERS):
        return "program", "very_long_program_signal"

    # Temporary exhibitions remain dated events even when they run for months.
    if category_id == "exposiciones" or "exposición temporal" in text:
        return "event", "dated_exhibition"

    # Flexible offers are reusable experiences, not merely long-running museum content.
    if days >= 90 and category_id == "museos" and any(marker in title_text for marker in FLEXIBLE_TITLE_MARKERS):
        return "flexible_offer", "long_running_reusable_museum_offer"

    return "event", "dated_event"


def apply_editorial_classification(dataset: dict) -> dict:
    reference = date.fromisoformat(dataset["publication_date"])
    priority = {"event": 0, "program": 1, "flexible_offer": 2, "course": 3}

    for event in dataset["events"]:
        event_type, reason = classify_editorial(event)
        event["event_type"] = event_type
        event["editorial"] = {
            "classification": event_type,
            "reason": reason,
            "duration_days": duration_days(event),
        }

    def sort_key(event: dict) -> tuple:
        start, _ = event_dates(event)
        effective = max(start or reference, reference)
        return (priority.get(event.get("event_type"), 9), effective.isoformat(), event.get("title") or "")

    dataset["events"].sort(key=sort_key)
    return dataset


def deduplicate_dataset(dataset: dict) -> tuple[dict, int]:
    unique: dict[str, dict] = {}
    duplicates = 0
    for event in dataset["events"]:
        event_id = event.get("id")
        if event_id in unique:
            duplicates += 1
            continue
        unique[event_id] = event

    dataset["events"] = list(unique.values())
    return dataset, duplicates


def refresh_counts(dataset: dict) -> dict:
    events = dataset["events"]
    dataset["counts"] = {
        "total": len(events),
        "events": sum(event.get("event_type") == "event" for event in events),
        "courses": sum(event.get("event_type") == "course" for event in events),
        "flexible_offers": sum(event.get("event_type") == "flexible_offer" for event in events),
        "programs": sum(event.get("event_type") == "program" for event in events),
    }
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--look-ahead-days", type=int, default=14)
    args = parser.parse_args()

    rows = fetch_rows()
    dataset = build_dataset(rows, look_ahead_days=args.look_ahead_days)
    dataset, duplicates = deduplicate_dataset(dataset)
    dataset = apply_editorial_classification(dataset)
    dataset = refresh_counts(dataset)
    for event in dataset["events"]:
        event["source_url"] = SOURCE_URL
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = dataset["counts"]
    print(
        f"Gijón XHTML rows: {len(rows)}; total: {counts['total']}; "
        f"eventos: {counts['events']}; programas: {counts['programs']}; "
        f"ofertas flexibles: {counts['flexible_offers']}; duplicados eliminados: {duplicates}"
    )


if __name__ == "__main__":
    main()
