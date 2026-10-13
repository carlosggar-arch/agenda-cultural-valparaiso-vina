from __future__ import annotations

import copy
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_high_value_sources import extract_barjola, extract_laboral, is_delegated_source, merge
from validate_high_value_refresh import (
    DATASETS,
    canonical_digest,
    selected_datasets,
    validate_dataset,
)


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


def test_gijon_high_value_sources_are_delegated_to_core() -> None:
    assert is_delegated_source({"dataset": "gijon"})
    assert not is_delegated_source({"dataset": "valparaiso"})


def test_public_validator_does_not_manage_core_gijon_events() -> None:
    year = future_year("Europe/Madrid")
    canonical = {
        "id": "core-gijon-barjola-test",
        "title": "Exposición canónica de prueba",
        "event_type": "event",
        "source_id": "museo_barjola",
        "schedule": {"start": f"{year}-09-01", "end": f"{year}-09-30"},
        "location": {"city": "Gijón"},
    }
    dataset = {"events": [copy.deepcopy(canonical)], "counts": {}}
    report = validate_dataset("gijon", dataset)
    assert report["managed_before"] == 0
    assert dataset["events"] == [canonical]
    assert dataset["counts"]["total"] == 1


def test_valpo_validation_target_does_not_include_gijon() -> None:
    targets = selected_datasets()
    assert targets == [("valparaiso", DATASETS["valparaiso"])]
    assert ("gijon", DATASETS["gijon"]) not in targets


def test_multicity_validation_requires_explicit_opt_in() -> None:
    assert selected_datasets("valparaiso", all_cities=True) == list(DATASETS.items())


def _high_value_event(
    event_id: str,
    source_id: str,
    title: str,
    *,
    day: str,
) -> dict:
    return {
        "id": event_id,
        "title": title,
        "event_type": "event",
        "source_id": source_id,
        "source_url": f"https://example.test/{event_id}",
        "schedule": {
            "mode": "single",
            "start": f"{day}T20:00:00-03:00",
            "end": f"{day}T22:00:00-03:00",
            "timezone": "America/Santiago",
            "occurrences": [],
        },
        "location": {"city": "Valparaíso", "venue": "Sala de prueba"},
        "editorial": {},
    }


def test_unique_high_value_duplicate_records_replayable_claim_idempotently() -> None:
    year = future_year("America/Santiago")
    day = f"{year}-11-20"
    survivor = _high_value_event(
        "agenda_survivor",
        "independent_source",
        "Full y la música de Fulano en Teatro Mauri",
        day=day,
    )
    duplicate = _high_value_event(
        "agenda_managed",
        "portaltickets_valparaiso",
        "Full y la música de Fulano",
        day=day,
    )
    dataset = {"events": [copy.deepcopy(survivor), copy.deepcopy(duplicate)], "counts": {}}

    first = validate_dataset("valparaiso", dataset)
    second = validate_dataset("valparaiso", dataset)

    assert first["dropped"]["duplicate"] == 1
    assert second["dropped"]["duplicate"] == 0
    assert [event["id"] for event in dataset["events"]] == ["agenda_survivor"]
    claims = dataset["events"][0]["editorial"]["duplicate_sources"]
    assert len(claims) == 1
    assert claims[0]["id"] == "agenda_managed"
    assert claims[0]["input_event"] == duplicate
    assert claims[0]["input_sha256"] == canonical_digest(duplicate)


def test_ambiguous_high_value_duplicate_is_preserved_fail_closed() -> None:
    year = future_year("America/Santiago")
    day = f"{year}-11-21"
    duplicate = _high_value_event(
        "agenda_managed",
        "portaltickets_valparaiso",
        "Concierto extraordinario",
        day=day,
    )
    dataset = {
        "events": [
            _high_value_event(
                "agenda_survivor_a",
                "source_a",
                "Concierto extraordinario en Valparaíso",
                day=day,
            ),
            _high_value_event(
                "agenda_survivor_b",
                "source_b",
                "Concierto extraordinario en sala central",
                day=day,
            ),
            copy.deepcopy(duplicate),
        ],
        "counts": {},
    }

    report = validate_dataset("valparaiso", dataset)

    assert report["dropped"]["duplicate"] == 0
    assert report["ambiguous_duplicates_preserved"] == 1
    assert {event["id"] for event in dataset["events"]} == {
        "agenda_survivor_a",
        "agenda_survivor_b",
        "agenda_managed",
    }
    assert all(
        not (event.get("editorial") or {}).get("duplicate_sources")
        for event in dataset["events"]
    )


def main() -> None:
    test_laboral_requires_source_context_and_explicit_session()
    test_barjola_date_ranges()
    test_merge_is_idempotent()
    test_gijon_high_value_sources_are_delegated_to_core()
    test_public_validator_does_not_manage_core_gijon_events()
    test_valpo_validation_target_does_not_include_gijon()
    test_multicity_validation_requires_explicit_opt_in()
    test_unique_high_value_duplicate_records_replayable_claim_idempotently()
    test_ambiguous_high_value_duplicate_is_preserved_fail_closed()
    print("HIGH_VALUE_SOURCE_TESTS_OK")


if __name__ == "__main__":
    main()
