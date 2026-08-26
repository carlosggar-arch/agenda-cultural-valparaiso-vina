from __future__ import annotations

import copy

from apply_content_quality_guard import (
    apply_guard,
    canonical_exhibition_title,
    clean_html_text,
    configured_datasets,
    recover_generic_title,
)


def event(**overrides):
    base = {
        "id": "event-1",
        "title": "Evento válido",
        "event_type": "event",
        "primary_category": {"id": "exposiciones", "label": "Exposiciones"},
        "categories": [{"id": "exposiciones", "label": "Exposiciones"}],
        "schedule": {"mode": "dated", "start": "2026-08-18T10:00:00-04:00", "end": None},
        "location": {"venue_id": None, "venue": "Museo Palacio Rioja", "city": "Viña del Mar"},
        "price": {"is_free": True, "display_text": "Gratis"},
        "links": {"official": "https://example.org/event", "source": "https://example.org/event"},
        "source_name": "Fuente oficial",
        "source_url": "https://example.org/event",
        "public_status": {"source_official": True, "information_completeness": "complete"},
        "description": "Descripción válida.",
        "image": {"url": None, "alt": None},
    }
    base.update(overrides)
    return base


def test_html_is_removed() -> None:
    raw = '<p>“Nebulosa carina” es una muestra.</p>\\\n'
    assert clean_html_text(raw) == '“Nebulosa carina” es una muestra.'
    assert clean_html_text(r'<p>Texto limpio.</p>\n') == 'Texto limpio.'
    assert clean_html_text('Texto limpio. n') == 'Texto limpio.'
    dataset = {"events": [event(description=raw)], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"][0]["description"] == '“Nebulosa carina” es una muestra.'
    assert changes["html_cleaned"] == ["event-1"]


def test_recovers_les_esperamos_from_explicit_activity_phrase() -> None:
    sample = event(
        id="bonsai",
        title="Les esperamos",
        location={"venue_id": "palacio-vergara", "venue": "Palacio Vergara", "city": "Viña del Mar"},
        description=(
            "El Municipio de Cuidados de Viña del Mar invita a la ceremonia de inauguración de la "
            "Muestra 2026 de la Corporación Quinta Bonsái, el viernes 28 de agosto, a las 16:00 horas."
        ),
        image={"url": "https://example.org/bonsai.jpg", "alt": "Les esperamos"},
    )
    recovered, reason = recover_generic_title(sample)
    assert recovered == "Muestra 2026 de la Corporación Quinta Bonsái"
    assert reason == "explicit_activity_phrase_in_description"
    dataset = {"events": [sample], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"][0]["title"] == "Muestra 2026 de la Corporación Quinta Bonsái"
    assert dataset["events"][0]["image"]["alt"] == "Muestra 2026 de la Corporación Quinta Bonsái"
    assert changes["titles_recovered"][0]["id"] == "bonsai"


def test_consolidates_same_exhibition_same_venue_and_keeps_image() -> None:
    official = event(
        id="official",
        title="Exposición temporal // A veces un mar dulce",
        location={"venue_id": None, "venue": "Museo Palacio Rioja", "city": "Viña del Mar"},
        source_url="https://visitavina.munivina.cl/actividad/a-veces-un-mar-dulce/",
        links={"official": "https://visitavina.munivina.cl/actividad/a-veces-un-mar-dulce/", "source": "https://visitavina.munivina.cl/actividad/a-veces-un-mar-dulce/"},
        public_status={"source_official": False, "information_completeness": "complete"},
        description="Exposición temporal // A veces un mar dulce. El eje curatorial es el concepto de balneario.",
        image={"url": None, "alt": None},
    )
    social = event(
        id="social",
        title="A veces un mar dulce",
        location={"venue_id": "museo-palacio-rioja", "venue": "Museo Palacio Rioja, Viña del Mar", "city": "Viña del Mar"},
        source_url="https://www.instagram.com/p/example/",
        links={"official": "https://www.instagram.com/p/example/", "source": "https://www.instagram.com/p/example/"},
        public_status={"source_official": True, "information_completeness": "complete"},
        description="“A veces un mar dulce” llegó al Museo Palacio Rioja.",
        image={"url": "https://example.org/a-veces.jpg", "alt": "Museo Palacio Rioja"},
    )
    assert canonical_exhibition_title(official["title"]) == canonical_exhibition_title(social["title"])
    dataset = {"events": [official, social], "counts": {"total": 2}}
    changes = apply_guard(dataset)
    assert len(dataset["events"]) == 1
    kept = dataset["events"][0]
    assert kept["id"] == "official"
    assert kept["title"] == "A veces un mar dulce"
    assert kept["image"]["url"] == "https://example.org/a-veces.jpg"
    assert changes["duplicates_consolidated"][0]["removed_ids"] == ["social"]
    assert dataset["counts"]["total"] == 1


def test_does_not_merge_same_title_in_different_venues() -> None:
    first = event(id="a", title="A veces un mar dulce")
    second = copy.deepcopy(first)
    second["id"] = "b"
    second["location"] = {"venue_id": "otro", "venue": "Otro museo", "city": "Viña del Mar"}
    dataset = {"events": [first, second], "counts": {"total": 2}}
    apply_guard(dataset)
    assert len(dataset["events"]) == 2


def test_quarantines_unrecoverable_generic_title() -> None:
    bad = event(id="bad", title="Les esperamos", description="Visítanos este fin de semana.")
    dataset = {"events": [bad], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"][0]["id"] == "bad"
    assert dataset["counts"]["total"] == 0


def test_quarantines_calendar_navigation_copy() -> None:
    bad = event(
        id="gijon-empty-state",
        title="0 eventos encontrados. No hay eventos programados. No hay eventos programados. Navegación de vistas",
        location={"venue_id": None, "venue": "El Huerto Espacio Escénico", "city": "Gijón"},
    )
    dataset = {"publication_date": "2026-08-19", "events": [bad], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"][0]["reason"] == "calendar_navigation_or_empty_state"


def test_removes_expired_event_against_publication_date() -> None:
    past = event(
        id="past-campus",
        title="Campus de Verano de La Laboral 2026",
        schedule={"mode": "single", "start": "2026-06-30T09:00:00+02:00", "end": None, "occurrences": []},
        location={"venue_id": None, "venue": "Laboral Ciudad de la Cultura", "city": "Gijón"},
    )
    dataset = {"publication_date": "2026-08-19", "events": [past], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["expired_removed"][0]["id"] == "past-campus"


def test_prunes_past_occurrences_and_keeps_future_session() -> None:
    recurring = event(
        id="recurring",
        title="Visita guiada recurrente",
        schedule={
            "mode": "multi_session",
            "start": "2026-08-18T10:00:00+02:00",
            "end": "2026-08-21T10:00:00+02:00",
            "occurrences": [
                {"start": "2026-08-18T10:00:00+02:00", "end": "2026-08-18T11:00:00+02:00"},
                {"start": "2026-08-20T10:00:00+02:00", "end": "2026-08-20T11:00:00+02:00"},
            ],
        },
    )
    dataset = {"publication_date": "2026-08-19", "events": [recurring], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert len(dataset["events"]) == 1
    occurrences = dataset["events"][0]["schedule"]["occurrences"]
    assert len(occurrences) == 1
    assert occurrences[0]["start"].startswith("2026-08-20")
    assert changes["past_occurrences_pruned"] == [{"id": "recurring", "count": 1}]


def test_quarantines_monthly_program_overview_without_concrete_event() -> None:
    overview = event(
        id="monthly-overview",
        title="AGOSTO EN CENTRO DE INVESTIGACIÓN TEATRO LA PESTE",
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Horario por confirmar"},
        description="Les invitamos a ser parte de toda nuestra programación. Revisa la programación en este carrusel.",
    )
    dataset = {"events": [overview], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"][0]["reason"] == "monthly_program_overview_without_event_schedule"


def test_quarantines_anniversary_news_without_concrete_event() -> None:
    news = event(
        id="anniversary-news",
        title="Un Año de Cultura y Reencuentro en el Teatro Municipal de Viña del Mar",
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Horario por confirmar"},
        description="Hoy celebramos que hace un año el emblemático teatro reabrió sus puertas.",
    )
    dataset = {"events": [news], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"][0]["reason"] == "institutional_news_or_retrospective_without_event_schedule"


def test_quarantines_visitation_statistics_news_without_concrete_event() -> None:
    news = event(
        id="visitation-news",
        title="Más de 50 mil personas visitaron museos en estas vacaciones de invierno",
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Fecha por confirmar"},
        description="Más de 50 mil personas visitaron museos durante estas vacaciones de invierno.",
    )
    dataset = {"events": [news], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"][0]["reason"] == "institutional_news_or_retrospective_without_event_schedule"


def test_quarantines_deadline_only_submission_call_even_if_deadline_was_parsed_as_schedule() -> None:
    call = event(
        id="photo-call-valpo",
        title="Envía tu foto hasta el: 24/08",
        location={"venue_id": "mhnv", "venue": "Museo de Historia Natural de Valparaíso", "city": "Valparaíso"},
        schedule={"mode": "single", "start": "2026-08-24T23:59:00-04:00", "end": None, "occurrences": []},
        description="¡Nueva convocatoria! ¿Tienes fotografías guardadas de 1980 a 2026? Envía tu foto hasta el 24/08.",
    )
    dataset = {"events": [call], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"] == [{
        "id": "photo-call-valpo",
        "title": "Envía tu foto hasta el: 24/08",
        "reason": "call_for_submissions_deadline_not_event",
    }]


def test_quarantines_description_led_submission_call_without_attendance_schedule() -> None:
    call = event(
        id="story-call-gijon",
        title="Premio de relato 2026",
        location={"venue_id": None, "venue": "Centro Cultural Municipal", "city": "Gijón"},
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Fecha por confirmar"},
        description="Nueva convocatoria para autores. Postulaciones abiertas hasta el 30/09. Presenta tu relato en línea.",
    )
    dataset = {"events": [call], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"][0]["reason"] == "call_for_submissions_deadline_not_event"



def test_quarantines_administrative_application_support_without_event_schedule() -> None:
    admin = event(
        id="fund-support-valpo",
        title="¿Quieres postular a los Fondos de Cultura 2027 y necesitas nuestra carta de apoyo?",
        location={"venue_id": None, "venue": "Valpo Cultura", "city": "Valparaíso"},
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Fecha por confirmar"},
        description="Ya se encuentra abierta la convocatoria para solicitar cartas de apoyo municipal. Este respaldo puede fortalecer tu propuesta.",
    )
    dataset = {"events": [admin], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"] == [{
        "id": "fund-support-valpo",
        "title": "¿Quieres postular a los Fondos de Cultura 2027 y necesitas nuestra carta de apoyo?",
        "reason": "administrative_application_support_not_event",
    }]


def test_quarantines_equivalent_application_support_in_another_city() -> None:
    admin = event(
        id="fund-support-gijon",
        title="¿Vas a postular a ayudas culturales y necesitas carta de apoyo?",
        location={"venue_id": None, "venue": "Centro Municipal", "city": "Gijón"},
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Fecha por confirmar"},
        description="Solicita una carta de apoyo institucional para tu postulación.",
    )
    dataset = {"events": [admin], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"][0]["reason"] == "administrative_application_support_not_event"


def test_keeps_scheduled_information_session_about_applications() -> None:
    real = event(
        id="scheduled-funding-talk",
        title="Charla: Cómo postular a Fondos de Cultura 2027",
        schedule={"mode": "single", "start": "2026-09-03T18:00:00-04:00", "end": "2026-09-03T19:30:00-04:00", "occurrences": []},
        description="Sesión informativa para postular y solicitar cartas de apoyo. La charla se realizará el 03/09 a las 18:00.",
    )
    dataset = {"events": [real], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert [item["id"] for item in dataset["events"]] == ["scheduled-funding-talk"]
    assert changes["quarantined"] == []


def test_keeps_cultural_event_that_only_mentions_funding_support() -> None:
    real = event(
        id="funded-cultural-event",
        title="Concierto Nuevas Voces",
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Horario por confirmar"},
        description="Proyecto financiado por Fondos de Cultura y respaldado mediante una carta de apoyo municipal.",
    )
    dataset = {"events": [real], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert [item["id"] for item in dataset["events"]] == ["funded-cultural-event"]
    assert changes["quarantined"] == []

def test_keeps_real_scheduled_activity_with_application_deadline() -> None:
    real = event(
        id="scheduled-workshop",
        title="Taller de fotografía documental",
        schedule={"mode": "single", "start": "2026-08-30T18:00:00-04:00", "end": "2026-08-30T20:00:00-04:00", "occurrences": []},
        description="Nueva convocatoria para participar. Inscripciones hasta el 24/08. El taller se realizará el 30/08 a las 18:00.",
    )
    dataset = {"events": [real], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert [item["id"] for item in dataset["events"]] == ["scheduled-workshop"]
    assert changes["quarantined"] == []


def test_does_not_quarantine_real_scheduled_anniversary_event() -> None:
    real = event(
        id="real-anniversary",
        title="Concierto de aniversario",
        schedule={"mode": "single", "start": "2026-08-28T19:00:00-04:00", "end": None, "occurrences": []},
        description="Celebramos un año con un concierto en vivo.",
    )
    dataset = {"events": [real], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert [item["id"] for item in dataset["events"]] == ["real-anniversary"]
    assert changes["quarantined"] == []


def test_registry_exposes_both_current_city_datasets() -> None:
    configured = dict(configured_datasets())
    assert "valparaiso" in configured
    assert "gijon" in configured
    assert configured["valparaiso"].name == "agenda_web.json"
    assert configured["gijon"].as_posix().endswith("app/data/gijon/agenda_web.json")


def main() -> None:
    test_html_is_removed()
    test_recovers_les_esperamos_from_explicit_activity_phrase()
    test_consolidates_same_exhibition_same_venue_and_keeps_image()
    test_does_not_merge_same_title_in_different_venues()
    test_quarantines_unrecoverable_generic_title()
    test_quarantines_calendar_navigation_copy()
    test_removes_expired_event_against_publication_date()
    test_prunes_past_occurrences_and_keeps_future_session()
    test_quarantines_monthly_program_overview_without_concrete_event()
    test_quarantines_anniversary_news_without_concrete_event()
    test_quarantines_visitation_statistics_news_without_concrete_event()
    test_quarantines_deadline_only_submission_call_even_if_deadline_was_parsed_as_schedule()
    test_quarantines_description_led_submission_call_without_attendance_schedule()
    test_quarantines_administrative_application_support_without_event_schedule()
    test_quarantines_equivalent_application_support_in_another_city()
    test_keeps_scheduled_information_session_about_applications()
    test_keeps_cultural_event_that_only_mentions_funding_support()
    test_keeps_real_scheduled_activity_with_application_deadline()
    test_does_not_quarantine_real_scheduled_anniversary_event()
    test_registry_exposes_both_current_city_datasets()
    print("CONTENT_QUALITY_GUARD_TESTS_OK")


if __name__ == "__main__":
    main()
