from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from update_gijon import build_dataset

SOURCE_URL = "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML"


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
            text = " ".join("".join(self.current_cell).split())
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
        items.append(dict(zip(headers, row)))
    if not items:
        raise ValueError("No se pudieron extraer eventos de la tabla XHTML de Gijón")
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--look-ahead-days", type=int, default=14)
    args = parser.parse_args()

    rows = fetch_rows()
    dataset = build_dataset(rows, look_ahead_days=args.look_ahead_days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Gijón XHTML rows: {len(rows)}; dataset: {len(dataset['events'])} entradas")


if __name__ == "__main__":
    main()
