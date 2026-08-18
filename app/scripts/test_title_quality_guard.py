from __future__ import annotations

import copy

from apply_title_quality_guard import apply_guard, recover_explicit_title, suspicious_venue_title


def bad_palacio_rioja_event() -> dict:
    return {
        "id": "agenda_test_palacio_rioja",
        "title": "Museo Palacio Rioja",
        "event_type": "event",
        "primary_category": {"id": "ferias-gastronomia", "label": "Ferias y gastronomía"},
        "categories": [{"id": "ferias-gastronomia", "label": "Ferias y gastronomía"}],
        "location": {"venue": "Museo Palacio Rioja", "city": "Viña del Mar"},
        "source_name": "Museo Palacio Rioja",
        "organizer": "Museo Palacio Rioja",
        "description": "🌊 “A veces un mar dulce” llegó al Museo Palacio Rioja. Esta exposición reúne las obras de Rocío Acevedo y Josefina Mercado.",
    }


def test_recovers_explicit_activity_name_and_category() -> None:
    event = bad_palacio_rioja_event()
    assert suspicious_venue_title(event)
    title, reason = recover_explicit_title(event)
    assert title == "A veces un mar dulce"
    assert reason == "explicit_quoted_activity_in_description"

    dataset = {"events": [event]}
    changes = apply_guard(dataset)
    assert len(changes) == 1
    fixed = dataset["events"][0]
    assert fixed["title"] == "A veces un mar dulce"
    assert fixed["primary_category"] == {"id": "exposiciones", "label": "Exposiciones"}
    assert fixed["categories"] == [{"id": "exposiciones", "label": "Exposiciones"}]
    assert fixed["editorial"]["title_original"] == "Museo Palacio Rioja"
    assert fixed["editorial"]["title_recovered"] is True


def test_does_not_rewrite_legitimate_title_containing_venue() -> None:
    event = bad_palacio_rioja_event()
    event["title"] = "Domingo de danza en el Palacio Rioja"
    before = copy.deepcopy(event)
    assert not suspicious_venue_title(event)
    assert apply_guard({"events": [event]}) == []
    assert event == before


def test_does_not_guess_without_explicit_title_evidence() -> None:
    event = bad_palacio_rioja_event()
    event["description"] = "El museo tendrá actividades especiales este domingo. Revisa horarios antes de asistir."
    before = copy.deepcopy(event)
    assert suspicious_venue_title(event)
    assert recover_explicit_title(event) == (None, None)
    assert apply_guard({"events": [event]}) == []
    assert event == before


def test_ignores_unrelated_quoted_phrase() -> None:
    event = bad_palacio_rioja_event()
    event["description"] = "El museo invita a visitar sus salas. El lema institucional es “Patrimonio para todos”."
    assert recover_explicit_title(event) == (None, None)


def main() -> None:
    test_recovers_explicit_activity_name_and_category()
    test_does_not_rewrite_legitimate_title_containing_venue()
    test_does_not_guess_without_explicit_title_evidence()
    test_ignores_unrelated_quoted_phrase()
    print("TITLE_QUALITY_GUARD_TESTS_OK")


if __name__ == "__main__":
    main()
