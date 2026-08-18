from __future__ import annotations

import copy
from datetime import datetime
from zoneinfo import ZoneInfo

from refresh_portaltickets_editorial import (
    SOURCE_ID,
    apply_detail,
    clean_public_title,
    parse_detail_markup,
    parse_markup,
    refresh_dataset,
)
from validate_portaltickets_editorial import validate_dataset


def future_year() -> int:
    return datetime.now(ZoneInfo("America/Santiago")).year + 1


def test_card_binding_geography_and_ticket_url() -> None:
    year = future_year()
    markup = f'''<div><h3>ALMA PAJARA EN TEATRO MAURI SCD VALPARAISO</h3>
    <p>Jueves 20 de agosto {year}, 19:00</p><p>Teatro Mauri SCD, Valparaíso</p>
    <a href="/tickets/evento/alma-pajara">TICKETS AQUÍ</a></div>
    <div><h3>MAREJADA 2026: SHOWCASES EN CENTRO CULTURAL SAN ANTONIO</h3>
    <p>Viernes 21 de agosto {year}, 18:30</p><p>Centro Cultural San Antonio, San Antonio</p>
    <a href="/tickets/evento/marejada">TICKETS AQUÍ</a></div>
    <div><h3>CITY NOISE EN JOURNAL, VIÑA DEL MAR</h3>
    <p>Viernes 21 de agosto {year}, 22:00</p><p>Cafe Journal, Viña del Mar</p>
    <a href="/tickets/evento/city-noise">TICKETS AQUÍ</a></div>'''
    events, stats = parse_markup(markup)
    assert len(events) == 2, (events, stats)
    assert events[0]["title"].startswith("ALMA PAJARA")
    assert events[0]["location"]["venue"] == "Teatro Mauri SCD, Valparaíso"
    assert events[0]["links"]["tickets"].endswith("/tickets/evento/alma-pajara")
    assert events[0]["links"]["source"] == events[0]["links"]["tickets"]
    assert events[0]["description"] is None
    assert events[0]["public_status"]["source_official"] is False
    assert events[0]["organizer"] is None
    assert events[1]["location"]["city"] == "Viña del Mar"
    assert stats["out_of_scope"] == 1


def test_shifted_mobile_copy_is_rejected() -> None:
    year = future_year()
    markup = f'''<div><h3>ALMA PAJARA EN TEATRO MAURI SCD VALPARAISO</h3><p>Jueves 20 de agosto {year}, 19:00</p>
    <p>Teatro Mauri SCD, Valparaíso</p><a href="/tickets/evento/alma">TICKETS AQUÍ</a></div>
    <div><p>Teatro Mauri SCD, Av. Alemania 6985, Valparaíso</p><p>Jueves 20 de agosto {year}, 19:00</p>
    <p>PORTAVOZ EN PATIO SÓCRATES, VALPARAÍSO</p><a href="/tickets/evento/portavoz">TICKETS AQUÍ</a></div>'''
    events, stats = parse_markup(markup)
    assert len(events) == 1, (events, stats)
    assert events[0]["title"].startswith("ALMA PAJARA")
    assert stats["invalid_card"] == 1


def test_catalog_link_is_not_accepted_as_individual_ticket() -> None:
    year = future_year()
    markup = f'''<div><h3>PUERTO ORQUESTA EN TEATRO MAURI SCD, VALPARAÍSO</h3>
    <p>Sábado 29 de agosto {year}, 19:30</p><p>Teatro Mauri SCD, Valparaíso</p>
    <a href="/tickets/R05">TICKETS AQUÍ</a></div>'''
    events, stats = parse_markup(markup)
    assert events == []
    assert stats["no_individual_ticket"] == 1


def test_music_classification_when_explicit() -> None:
    year = future_year()
    markup = f'''<div><h3>PUERTO ORQUESTA EN TEATRO MAURI SCD, VALPARAÍSO</h3>
    <p>Sábado 29 de agosto {year}, 19:30</p><p>Teatro Mauri SCD, Valparaíso</p>
    <a href="/tickets/evento/puerto-orquesta">TICKETS AQUÍ</a></div>'''
    events, _ = parse_markup(markup)
    assert events[0]["primary_category"] == {"id": "musica", "label": "Música"}


def test_redundant_venue_suffix_is_removed_but_real_title_is_preserved() -> None:
    venue = "Teatro Mauri SCD, Valparaíso"
    assert clean_public_title("QUILAPAYUN EN TEATRO MAURI SCD VALPARAÍSO", venue, "Valparaíso") == "QUILAPAYUN"
    assert clean_public_title("LOS SANTOS DUMONT: CANCIONES CHILENAS EN TEATRO MAURI SCD", venue, "Valparaíso") == "LOS SANTOS DUMONT: CANCIONES CHILENAS"
    assert clean_public_title("EL MAURI EN EL MAURI", venue, "Valparaíso") == "EL MAURI EN EL MAURI"
    assert clean_public_title("EL MAURI EN EL MAURI, VALPARAISO", venue, "Valparaíso") == "EL MAURI EN EL MAURI"


def test_detail_parser_keeps_useful_description_and_detects_partial_availability() -> None:
    markup = '''<h1>QUILAPAYUN EN TEATRO MAURI SCD VALPARAÍSO</h1>
    <h3>TICKETS DISPONIBLES:</h3>
    <div>PLATEA BAJA: $15.000 + Cargo</div><div>AGOTADA</div>
    <div>GALERIA: $10.000 + Cargo</div><div>Comprar o Regalar</div>
    <h4>Descripción</h4>
    <p>Quilapayún vuelve a Valparaíso con un concierto que recorre sus canciones más emblemáticas.</p>
    <p>Este concierto forma parte del Ciclo Inaugural del Teatro Mauri SCD, histórico recinto porteño.</p>
    <h4>POLÍTICAS DE REEMBOLSO</h4>'''
    detail = parse_detail_markup(markup)
    assert detail["description"] == "Quilapayún vuelve a Valparaíso con un concierto que recorre sus canciones más emblemáticas."
    assert detail["sold_out"] is False
    assert detail["registration_open"] is True
    assert detail["partial_availability"] is True
    assert detail["price_min"] == 10000
    assert detail["price_max"] == 15000
    assert detail["price_text"] == "$10.000–$15.000 · Algunos sectores agotados"


def test_description_template_prefix_is_removed_without_losing_real_copy() -> None:
    markup = '''<h4>Descripción</h4>
    <p>AGREGA AQUÍ LA DESCRIPCIÓN DEL EVENTO Macrobia y Piel vivirán un evento único este 3 de octubre en Viña del Mar.</p>'''
    detail = parse_detail_markup(markup)
    assert detail["description"] == "Macrobia y Piel vivirán un evento único este 3 de octubre en Viña del Mar."


def test_detail_parser_marks_fully_sold_event_and_apply_detail_surfaces_it() -> None:
    year = future_year()
    listing = f'''<div><h3>PAULA RIVAS EN TEATRO MAURI SCD, VALPARAISO</h3>
    <p>Sábado 26 de septiembre {year}, 20:00</p><p>Teatro Mauri SCD, Valparaíso</p>
    <a href="/evento/paularivas">TICKETS AQUÍ</a></div>'''
    events, _ = parse_markup(listing)
    detail_markup = '''<h3>TICKETS DISPONIBLES:</h3>
    <div>PLATEA BAJA: $15.000 + Cargo</div><div>AGOTADA</div>
    <div>PLATEA ALTA: $12.000 + Cargo</div><div>AGOTADA</div>
    <h4>Descripción</h4><p>Paula Rivas presenta un concierto especial en Valparaíso.</p>'''
    detail = parse_detail_markup(detail_markup)
    assert detail["sold_out"] is True
    enriched = apply_detail(events[0], detail, verified_at="2026-08-18T08:00:00-04:00")
    assert enriched["title"] == "PAULA RIVAS"
    assert enriched["price"]["display_text"] == "Entradas agotadas"
    assert enriched["public_status"]["sold_out"] is True
    assert enriched["public_status"]["registration_open"] is False
    assert enriched["primary_category"] == {"id": "musica", "label": "Música"}


def test_refresh_removes_legacy_and_is_idempotent() -> None:
    year = future_year()
    markup = f'''<div><h3>PUERTO ORQUESTA EN TEATRO MAURI SCD, VALPARAÍSO</h3>
    <p>Sábado 29 de agosto {year}, 19:30</p><p>Teatro Mauri SCD, Valparaíso</p>
    <a href="/tickets/evento/puerto-orquesta">TICKETS AQUÍ</a></div>'''
    candidates, _ = parse_markup(markup)
    legacy = copy.deepcopy(candidates[0])
    legacy["id"] = "legacy"
    legacy["title"] = "Teatro Mauri SCD, Av. Alemania 6985, Valparaíso"
    legacy["editorial"]["reason"] = "high_value_source:portaltickets_valparaiso"
    base = {"id": "base", "title": "Otro evento", "source_id": "other", "event_type": "event", "schedule": {"start": f"{year}-08-30T12:00:00-04:00"}, "location": {"city": "Valparaíso"}}
    updated, stats = refresh_dataset({"events": [legacy, base], "counts": {}}, candidates, fetch_ok=True)
    assert stats["legacy_removed"] == 1
    assert stats["corrected_published"] == 1
    assert len([e for e in updated["events"] if e.get("source_id") == SOURCE_ID]) == 1
    updated2, stats2 = refresh_dataset(updated, candidates, fetch_ok=True)
    assert stats2["previous_corrected"] == 1
    assert len([e for e in updated2["events"] if e.get("source_id") == SOURCE_ID]) == 1


def test_fetch_failure_preserves_corrected_but_removes_legacy() -> None:
    year = future_year()
    markup = f'''<div><h3>PUERTO ORQUESTA EN TEATRO MAURI SCD, VALPARAÍSO</h3>
    <p>Sábado 29 de agosto {year}, 19:30</p><p>Teatro Mauri SCD, Valparaíso</p>
    <a href="/tickets/evento/puerto-orquesta">TICKETS AQUÍ</a></div>'''
    corrected, _ = parse_markup(markup)
    legacy = copy.deepcopy(corrected[0]); legacy["id"] = "legacy"; legacy["editorial"]["reason"] = "high_value_source:portaltickets_valparaiso"
    updated, stats = refresh_dataset({"events": [legacy, corrected[0]], "counts": {}}, [], fetch_ok=False)
    assert stats["legacy_removed"] == 1
    assert stats["previous_corrected"] == 1
    assert len(updated["events"]) == 1


def test_validator_rejects_legacy_crossed_record() -> None:
    year = future_year()
    bad = {
        "id": "bad", "title": "Teatro Mauri SCD, Av. Alemania 6985, Valparaíso", "source_id": SOURCE_ID,
        "organizer": "PortalTickets — Región de Valparaíso", "public_status": {"source_official": True},
        "editorial": {"reason": "high_value_source:portaltickets_valparaiso"},
        "links": {"tickets": "https://www.portaldisc.com/tickets/R05", "official": "https://www.portaldisc.com/tickets/R05"},
        "location": {"city": "Valparaíso", "venue": "PORTAVOZ EN PATIO SÓCRATES, VALPARAÍSO", "address": None},
        "schedule": {"start": f"{year}-08-20T19:00:00-04:00"}, "event_type": "event",
    }
    report = validate_dataset({"events": [bad]})
    assert report["failures"], report
    errors = set(report["failures"][0]["errors"])
    assert {"address_used_as_title", "secondary_source_marked_official", "legacy_editorial_reason", "missing_individual_ticket"} <= errors


def main() -> None:
    test_card_binding_geography_and_ticket_url()
    test_shifted_mobile_copy_is_rejected()
    test_catalog_link_is_not_accepted_as_individual_ticket()
    test_music_classification_when_explicit()
    test_redundant_venue_suffix_is_removed_but_real_title_is_preserved()
    test_detail_parser_keeps_useful_description_and_detects_partial_availability()
    test_description_template_prefix_is_removed_without_losing_real_copy()
    test_detail_parser_marks_fully_sold_event_and_apply_detail_surfaces_it()
    test_refresh_removes_legacy_and_is_idempotent()
    test_fetch_failure_preserves_corrected_but_removes_legacy()
    test_validator_rejects_legacy_crossed_record()
    print("PORTALTICKETS_EDITORIAL_TESTS_OK")


if __name__ == "__main__":
    main()
