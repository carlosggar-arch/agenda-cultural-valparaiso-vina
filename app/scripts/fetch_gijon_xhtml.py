from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from update_gijon import build_dataset

SOURCE_URL = "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML"
MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "ðŸ", "�", "\x81", "\x8d", "\x8f", "\x90", "\x9d")


def repair_mojibake(value: str) -> str:
    """Repair UTF-8 text that the XHTML export exposes through a legacy byte interpretation."""
    current = value
    for _ in range(3):
        if not any(marker in current for marker in MOJIBAKE_MARKERS):
            break
        repaired = None
        for encoding in ("latin1", "cp1252"):
            try:
                repaired = current.encode(encoding).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        if not repaired or repaired == current:
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


def deduplicate_dataset(dataset: dict) -> tuple[dict, int]:
    unique: dict[str, dict] = {}
    duplicates = 0
    for event in dataset["events"]:
        event_id = event.get("id")
        if event_id in unique:
            duplicates += 1
            continue
        unique[event_id] = event

    events = list(unique.values())
    dataset["events"] = events
    dataset["counts"] = {
        "total": len(events),
        "events": sum(event.get("event_type") == "event" for event in events),
        "courses": sum(event.get("event_type") == "course" for event in events),
        "flexible_offers": sum(event.get("event_type") == "flexible_offer" for event in events),
        "programs": sum(event.get("event_type") == "program" for event in events),
    }
    return dataset, duplicates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--look-ahead-days", type=int, default=14)
    args = parser.parse_args()

    rows = fetch_rows()
    dataset = build_dataset(rows, look_ahead_days=args.look_ahead_days)
    dataset, duplicates = deduplicate_dataset(dataset)
    for event in dataset["events"]:
        event["source_url"] = SOURCE_URL
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Gijón XHTML rows: {len(rows)}; dataset: {len(dataset['events'])} entradas; "
        f"duplicados eliminados: {duplicates}"
    )


if __name__ == "__main__":
    main()
