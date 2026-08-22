from datetime import date, timedelta

from apply_content_quality_guard import apply_guard
from fetch_gijon_xhtml import classify_editorial
from update_gijon import normalize_event, real_time, schedule_display


def make_event(*, title: str, days: int, venue: str, category: str, tags=None, event_type="event") -> dict:
    start = date(2026, 8, 15)
    end = start + timedelta(days=days)
    return {
        "id": f"test-{title}",
        "title": title,
        "event_type": event_type,
        "description": "",
        "primary_category": {"id": category, "label": category},
        "categories": [{"id": category, "label": category}],
        "tags": tags or [],
        "schedule": {"start": start.isoformat(), "end": end.isoformat(), "occurrences": []},
        "location": {"venue": venue, "city": "Gijón"},
    }


def check(event: dict, expected: str) -> None:
    actual, reason = classify_editorial(event)
    assert actual == expected, f"expected {expected}, got {actual} ({reason}) for {event['title']}"


def source_row(*, start_time: str, end_time: str) -> dict:
    return {
        "materia": "Cultural",
        "titulo": "Exposición de prueba",
        "field_estado_del_evento": "",
        "fechas": "2026-07-30 2026-08-27",
        "tipo": "Exposición",
        "etiquetas": "",
        "id": "test-hours",
        "alias": "https://www.gijon.es/exposicion-de-prueba",
        "hora_inicio": start_time,
        "hora_fin": end_time,
        "titulo_directorio": "Centro Municipal Integrado de prueba",
    }


def check_multi_day_source_hours() -> None:
    event = normalize_event(source_row(start_time="09:00", end_time="21:00"))
    assert event is not None
    schedule = event["schedule"]
    assert schedule["opening_time"] == "09:00"
    assert schedule["closing_time"] == "21:00"
    assert schedule["hours_confidence"] == "official_event_schedule"
    assert schedule["start"].startswith("2026-07-30T09:00:00")
    assert schedule["end"] == "2026-08-27"

    placeholder = normalize_event(source_row(start_time="00:00", end_time="23:59"))
    assert placeholder is not None
    assert "opening_time" not in placeholder["schedule"]
    assert "closing_time" not in placeholder["schedule"]


def check_shared_quality_guard() -> None:
    garbage = make_event(
        title="0 eventos encontrados. No hay eventos programados. Navegación de vistas de Evento",
        days=0,
        venue="El Huerto Espacio Escénico",
        category="teatro",
    )
    past = make_event(
        title="Campus de Verano de La Laboral 2026",
        days=0,
        venue="Laboral Ciudad de la Cultura",
        category="cursos-talleres",
    )
    past["schedule"] = {"start": "2026-06-30T09:00:00+02:00", "end": None, "occurrences": []}
    future = make_event(
        title="Concierto válido",
        days=0,
        venue="Teatro Jovellanos",
        category="musica",
    )
    future["schedule"] = {"start": "2026-08-20T20:00:00+02:00", "end": None, "occurrences": []}

    dataset = {
        "publication_date": "2026-08-19",
        "events": [garbage, past, future],
        "counts": {"total": 3},
    }
    changes = apply_guard(dataset)
    assert [event["title"] for event in dataset["events"]] == ["Concierto válido"]
    assert any(item["reason"] == "calendar_navigation_or_empty_state" for item in changes["quarantined"])
    assert any(item["id"] == past["id"] for item in changes["expired_removed"])


def main() -> None:
    assert real_time("00:00") is None
    assert real_time("23:59") is None
    assert real_time("18:30") == "18:30"
    assert schedule_display("2026-08-20", "2026-08-20", "00:00") == "2026-08-20"
    assert schedule_display("2026-08-20", "2026-08-30", "00:00") == "2026-08-20 – 2026-08-30"
    assert schedule_display("2026-08-20", "2026-08-20", "18:30") == "2026-08-20 · 18:30"
    check_multi_day_source_hours()

    check(
        make_event(
            title="Concierto de cámara",
            days=0,
            venue="Teatro Jovellanos",
            category="musica",
        ),
        "event",
    )
    check(
        make_event(
            title="Exposición temporal",
            days=35,
            venue="Centro de Cultura Antiguo Instituto",
            category="exposiciones",
        ),
        "event",
    )
    check(
        make_event(
            title="Cartelos n'asturianu (1976-2005)",
            days=221,
            venue="Muséu del Pueblu d'Asturies",
            category="exposiciones",
            tags=["Museos", "Exposición temporal"],
        ),
        "event",
    )
    check(
        make_event(
            title="Escena Amateur",
            days=800,
            venue="Gijón/Xixón",
            category="teatro",
            tags=["Super Evento (Programa)"],
            event_type="program",
        ),
        "program",
    )
    check(
        make_event(
            title="FETEN COMPAÑÍAS",
            days=7000,
            venue="Gijón/Xixón",
            category="teatro",
        ),
        "program",
    )
    check(
        make_event(
            title="Conoce el Muséu del Pueblu d'Asturies | Visitas comentadas",
            days=364,
            venue="Muséu del Pueblu d'Asturies",
            category="museos",
            tags=["Museos", "Turismo"],
        ),
        "flexible_offer",
    )
    check_shared_quality_guard()
    print("Gijón editorial classification, schedule and shared quality tests: OK")


if __name__ == "__main__":
    main()
