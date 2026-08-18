from __future__ import annotations

import copy

from apply_content_quality_guard import apply_guard, canonical_exhibition_title, clean_html_text, recover_generic_title


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
        source_url="https://visitavina.munivina.cl/actividad/a-veces-un-mar-dulce/",
        links={"official": "https://visitavina.munivina.cl/actividad/a-veces-un-mar-dulce/", "source": "https://visitavina.munivina.cl/actividad/a-veces-un-mar-dulce/"},
        public_status={"source_official": False, "information_completeness": "complete"},
        description="Exposición temporal // A veces un mar dulce. El eje curatorial es el concepto de balneario.",
        image={"url": None, "alt": None},
    )
    social = event(
        id="social",
        title="A veces un mar dulce",
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


def main() -> None:
    test_html_is_removed()
    test_recovers_les_esperamos_from_explicit_activity_phrase()
    test_consolidates_same_exhibition_same_venue_and_keeps_image()
    test_does_not_merge_same_title_in_different_venues()
    test_quarantines_unrecoverable_generic_title()
    print("CONTENT_QUALITY_GUARD_TESTS_OK")


if __name__ == "__main__":
    main()
