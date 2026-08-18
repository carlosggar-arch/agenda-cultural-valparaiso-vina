from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_high_value_sources import (
    extract_barjola,
    extract_explicit_spanish,
    extract_habitacion,
    extract_laboral,
    extract_mae,
    extract_picu,
    merge,
)

ROOT = Path(__file__).resolve().parents[2]


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


def test_laboral_requires_source_context_and_explicit_session() -> None:
    src = source("laboral_cinemateca", "gijon", "Gijón", "Europe/Madrid", "EUR", "cine", "Cine")
    year = future_year(src["timezone"])
    rows = [
        "Laboral Cinemateca de Gijón/Xixón",
        f"1 de septiembre {year} 19:00 h. Estaciones. Película de prueba",
        f"2 de septiembre {year} 17:30 h. Infantil y juvenil. Cine familiar de prueba",
    ]
    events = extract_laboral(src, rows)
    assert len(events) == 2, events
    assert all(item["location"]["city"] == "Gijón" for item in events)
    assert all(item["location"]["venue"] == "Laboral Ciudad de la Cultura" for item in events)
    assert events[0]["title"] == "Película de prueba"
    assert extract_laboral(src, [f"1 de septiembre {year} 19:00 h. Otro evento", "Gijón/Xixón"]) == []


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


def test_explicit_spanish_sources_never_infer_year() -> None:
    src = source("el_huerto_gijon", "gijon", "Gijón", "Europe/Madrid", "EUR", "teatro", "Teatro y danza")
    year = future_year(src["timezone"])
    events = extract_explicit_spanish(src, ["Y fuimos héroes", f"17 de marzo de {year} de 19:00 a 20:30"])
    assert len(events) == 1, events
    assert events[0]["title"] == "Y fuimos héroes"
    assert events[0]["schedule"]["start"].startswith(f"{year}-03-17T19:00")
    assert extract_explicit_spanish(src, ["Y fuimos héroes", "17 de marzo 19:00"]) == []

    comedy = source("el_percebe_comedy", "gijon", "Gijón", "Europe/Madrid", "EUR", "teatro", "Comedia")
    assert extract_explicit_spanish(comedy, ["Próximamente", "Show sin fecha"]) == []
    comedy_events = extract_explicit_spanish(comedy, ["Monólogo de prueba", f"8 de octubre de {year} a las 20:30"])
    assert len(comedy_events) == 1, comedy_events


def test_habitacion_calendar_full_date() -> None:
    src = source("la_habitacion_propia", "gijon", "Gijón", "Europe/Madrid", "EUR", "literatura", "Libros y charlas")
    year = future_year(src["timezone"])
    events = extract_habitacion(src, ["Presentación de libro", f"17 de marzo de {year} de 19:00 a 20:30"])
    assert len(events) == 1, events
    assert events[0]["title"] == "Presentación de libro"


def test_mae_requires_named_market_and_explicit_range() -> None:
    src = source("mae_gijon", "gijon", "Gijón", "Europe/Madrid", "EUR", "ferias", "Ferias y mercados")
    year = future_year(src["timezone"])
    rows = [
        "MERCADO ARTESANO Y ECOLÓGICO DE GIJÓN",
        "Plaza Mayor",
        f"12/09/{year} - 13/09/{year}",
    ]
    events = extract_mae(src, rows)
    assert len(events) == 1, events
    assert events[0]["title"] == "Mercado Artesano y Ecológico de Gijón"
    assert events[0]["schedule"]["mode"] == "multi_day"
    assert extract_mae(src, ["Otra feria", f"12/09/{year} - 13/09/{year}"]) == []


def test_picu_routes_and_rejections() -> None:
    src = source("picu_urriellu", "gijon", "Gijón", "Europe/Madrid", "EUR", "naturaleza", "Naturaleza y rutas")
    year = future_year(src["timezone"])
    rows = [
        f"12-07-{year} 7:00h Canal del Texu - Bulnes",
        f"19-07-{year} 8:00h Asamblea general",
        f"26/07/{year} Ruta sustituida por mal tiempo",
    ]
    events = extract_picu(src, rows)
    assert len(events) == 1, events
    assert events[0]["title"] == "Canal del Texu - Bulnes"
    assert events[0]["location"]["city"] == "Gijón"
    assert events[0]["schedule"]["start"].startswith(f"{year}-07-12T07:00")


def test_batch_registry_and_albeniz_existing_coverage() -> None:
    config = json.loads((ROOT / "app/data/high_value_sources.json").read_text(encoding="utf-8"))
    registry = {item["id"]: item for item in config["sources"]}
    expected = {
        "el_huerto_gijon", "el_percebe_comedy", "la_habitacion_propia", "mae_gijon", "picu_urriellu",
    }
    assert expected <= set(registry), registry
    assert all(registry[source_id]["mode"] == "monitor" for source_id in expected)
    assert all(registry[source_id]["required"] is False for source_id in expected)

    dataset = json.loads((ROOT / "app/data/gijon/agenda_web.json").read_text(encoding="utf-8"))
    source_ids = {str(item.get("id") or "") for item in dataset.get("sources", [])}
    event_sources = {str(item.get("source_id") or "") for item in dataset.get("events", [])}
    assert "teatro_albeniz_gijon" in source_ids | event_sources, "Teatro Albéniz should remain covered by the canonical Gijón handoff"


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
    test_laboral_requires_source_context_and_explicit_session()
    test_barjola_date_ranges()
    test_explicit_spanish_sources_never_infer_year()
    test_habitacion_calendar_full_date()
    test_mae_requires_named_market_and_explicit_range()
    test_picu_routes_and_rejections()
    test_batch_registry_and_albeniz_existing_coverage()
    test_merge_is_idempotent()
    print("HIGH_VALUE_SOURCE_TESTS_OK")


if __name__ == "__main__":
    main()
