from __future__ import annotations

import copy
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_high_value_sources import extract_barjola, extract_portal, merge


def source(source_id: str, dataset: str, city: str, timezone: str, currency: str, category_id: str, category_label: str) -> dict:
    return {
        "id": source_id,
        "name": source_id,
        "dataset": dataset,
        "city": city,
        "timezone": timezone,
        "currency": currency,
        "url": "https://example.test/source",
        "category_id": category_id,
        "category_label": category_label,
    }


def future_year(timezone: str) -> int:
    return datetime.now(ZoneInfo(timezone)).year + 1


def test_portal_strict_geography() -> None:
    src = source("portaltickets_valparaiso", "valparaiso", "Valparaíso", "America/Santiago", "CLP", "cultura", "Cultura")
    year = future_year(src["timezone"])
    rows = [
        "CONCIERTO A",
        f"Viernes 21 de agosto {year}, 19:00",
        "Teatro Puerto, Valparaíso",
        "TICKETS AQUÍ",
        "CONCIERTO B",
        f"Viernes 21 de agosto {year}, 20:00",
        "Centro Cultural San Antonio, San Antonio",
        "TICKETS AQUÍ",
        "CONCIERTO C",
        f"Sábado 22 de agosto {year}, 21:00",
        "Sala Viña, Viña del Mar",
    ]
    events = extract_portal(src, rows)
    assert len(events) == 2, events
    assert {item["location"]["city"] for item in events} == {"Valparaíso", "Viña del Mar"}
    assert all("San Antonio" not in item["location"]["venue"] for item in events)


def test_barjola_date_ranges() -> None:
    src = source("museo_barjola", "gijon", "Gijón", "Europe/Madrid", "EUR", "exposiciones", "Exposiciones")
    year = future_year(src["timezone"])
    rows = [
        f"03/07/{year} - 23/08/{year}",
        "Miraes prueba",
        "VVAA",
        f"10/04/{year} - 23/08/{year}",
        "El Palacio prueba",
        "Autor",
    ]
    events = extract_barjola(src, rows)
    assert len(events) == 2, events
    assert all(item["location"]["city"] == "Gijón" for item in events)
    assert all(item["schedule"]["mode"] == "multi_day" for item in events)


def test_merge_is_idempotent() -> None:
    src = source("museo_barjola", "gijon", "Gijón", "Europe/Madrid", "EUR", "exposiciones", "Exposiciones")
    year = future_year(src["timezone"])
    candidate = extract_barjola(src, [f"03/07/{year} - 23/08/{year}", "Miraes prueba"])[0]
    dataset = {"events": [], "counts": {}}
    added, duplicate = merge(dataset, [copy.deepcopy(candidate)])
    assert (added, duplicate) == (1, 0)
    added, duplicate = merge(dataset, [copy.deepcopy(candidate)])
    assert (added, duplicate) == (0, 1)
    assert dataset["counts"]["total"] == 1


def main() -> None:
    test_portal_strict_geography()
    test_barjola_date_ranges()
    test_merge_is_idempotent()
    print("HIGH_VALUE_SOURCE_TESTS_OK")


if __name__ == "__main__":
    main()
