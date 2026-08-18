from __future__ import annotations

from datetime import date

from ecoliderazgo_policy import departure_policy
import refresh_priority_zero_monitors as monitor


def target(target_id: str) -> dict:
    return next(item for item in monitor.TARGETS if item["id"] == target_id)


def test_ipa_past_and_future() -> None:
    today = date(2026, 8, 18)
    past = "<p>Yo no nací para amar</p><p>Location : Sala Teatro Ipa Jue, julio 30, 2026 7:00 PM</p>"
    row = monitor.classify(target("sala_teatro_ipa"), past, today)
    assert row["state"] == "verified_no_publishable_future"
    assert row["verified_inactive"] is True
    future = "<p>Nueva obra</p><p>Location : Sala Teatro Ipa Jue, agosto 27, 2026 7:00 PM</p>"
    row = monitor.classify(target("sala_teatro_ipa"), future, today)
    assert row["state"] == "future_detected"
    assert row["future_candidates"][0]["date"] == "2026-08-27"


def test_la_peste_requires_explicit_empty_or_future_date() -> None:
    today = date(2026, 8, 18)
    empty = "<h1>Tus Entradas para Teatro La Peste</h1><p>No hay eventos disponibles</p>"
    row = monitor.classify(target("teatro_la_peste"), empty, today)
    assert row["state"] == "verified_no_publishable_future"
    assert row["explicit_empty_state"] is True
    uncertain = "<h1>Tus Entradas para Teatro La Peste</h1><p>Próximamente</p>"
    assert monitor.classify(target("teatro_la_peste"), uncertain, today)["state"] == "indeterminate"


def test_ecoliderazgo_catalog_without_dates_has_no_publishable_event() -> None:
    today = date(2026, 8, 18)
    markup = """
    <h2>Nuestras próximas actividades</h2>
    <h4>Campamento Invernal</h4>
    <h4>Parque Nacional La Campana - Sector Ocoa</h4>
    <h4>Humedal de Batuco</h4>
    <h2>El Equipo de EcoLiderazgo</h2>
    """
    row = monitor.classify(target("ecoliderazgo"), markup, today)
    assert row["state"] == "verified_no_publishable_future", row
    assert row["verification_reason"] == "official_upcoming_catalog_has_no_explicit_future_date"


def test_ecoliderazgo_missing_origin_uses_source_default() -> None:
    today = date(2026, 8, 18)
    markup = """
    <h2>Nuestras próximas actividades</h2>
    <p>27 de agosto de 2026. Trekking Parque Nacional La Campana - Sector Ocoa.</p>
    <h2>El Equipo de EcoLiderazgo</h2>
    """
    row = monitor.classify(target("ecoliderazgo"), markup, today)
    assert row["state"] == "future_detected", row
    candidate = row["future_candidates"][0]
    assert candidate["date"] == "2026-08-27"
    assert candidate["departure_origin_scope"] == "Viña del Mar / Valparaíso"
    assert candidate["departure_origin_mode"] == "source_default"
    assert candidate["departure_origin_rule"] == "user_confirmed_ecoliderazgo_default"
    assert row["future_candidates_source_default_origin_count"] == 1


def test_ecoliderazgo_explicit_local_departure_wins() -> None:
    today = date(2026, 8, 18)
    markup = """
    <h2>Nuestras próximas actividades</h2>
    <p>Salida 29 de agosto de 2026 desde Valparaíso con destino al Cajón del Maipo.</p>
    <h2>El Equipo de EcoLiderazgo</h2>
    """
    row = monitor.classify(target("ecoliderazgo"), markup, today)
    assert row["state"] == "future_detected", row
    assert row["future_candidates"][0]["departure_origin_mode"] == "explicit_local"


def test_ecoliderazgo_explicit_nonlocal_departure_overrides_default() -> None:
    today = date(2026, 8, 18)
    markup = """
    <h2>Nuestras próximas actividades</h2>
    <p>Salida desde Santiago el 30 de agosto de 2026. Trekking Cajón del Maipo.</p>
    <h2>El Equipo de EcoLiderazgo</h2>
    """
    row = monitor.classify(target("ecoliderazgo"), markup, today)
    assert row["state"] == "future_unqualified_geography", row
    assert row["future_candidates"] == []
    candidate = row["future_candidates_unqualified_geography"][0]
    assert candidate["departure_origin_mode"] == "explicit_other"


def test_ecoliderazgo_policy_is_destination_agnostic() -> None:
    policy = departure_policy("Trekking Parque Nacional Cerro Castillo + Capillas de Mármol")
    assert policy["eligible"] is True
    assert policy["departure_origin_mode"] == "source_default"
    assert policy["departure_origin_scope"] == "Viña del Mar / Valparaíso"


def main() -> None:
    test_ipa_past_and_future()
    test_la_peste_requires_explicit_empty_or_future_date()
    test_ecoliderazgo_catalog_without_dates_has_no_publishable_event()
    test_ecoliderazgo_missing_origin_uses_source_default()
    test_ecoliderazgo_explicit_local_departure_wins()
    test_ecoliderazgo_explicit_nonlocal_departure_overrides_default()
    test_ecoliderazgo_policy_is_destination_agnostic()
    print("PRIORITY_ZERO_MONITORS_TESTS_OK")


if __name__ == "__main__":
    main()
