from __future__ import annotations

from datetime import date

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
    assert row["verified_inactive"] is False
    assert row["future_candidates"][0]["date"] == "2026-08-27"


def test_la_peste_requires_explicit_empty_or_future_date() -> None:
    today = date(2026, 8, 18)
    empty = "<h1>Tus Entradas para Teatro La Peste</h1><p>No hay eventos disponibles</p>"
    row = monitor.classify(target("teatro_la_peste"), empty, today)
    assert row["state"] == "verified_no_publishable_future"
    assert row["verified_inactive"] is True
    assert row["explicit_empty_state"] is True

    uncertain = "<h1>Tus Entradas para Teatro La Peste</h1><p>Próximamente</p>"
    row = monitor.classify(target("teatro_la_peste"), uncertain, today)
    assert row["state"] == "indeterminate"
    assert row["verified_inactive"] is False

    future = "<h1>Tus Entradas para Teatro La Peste</h1><p>Nueva función 2 de septiembre de 2026</p>"
    row = monitor.classify(target("teatro_la_peste"), future, today)
    assert row["state"] == "future_detected"
    assert row["verified_inactive"] is False


def test_ecoliderazgo_upcoming_catalog_without_dates_is_verified_zero() -> None:
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
    assert row["verified_inactive"] is True
    assert row["verification_reason"] == "official_upcoming_catalog_has_no_explicit_future_date_with_local_departure"


def test_ecoliderazgo_requires_local_departure_not_destination() -> None:
    today = date(2026, 8, 18)
    qualified = """
    <h2>Nuestras próximas actividades</h2>
    <p>Salida 27 de agosto de 2026. Punto de encuentro: Viña del Mar. Trekking Parque Nacional La Campana.</p>
    <h2>El Equipo de EcoLiderazgo</h2>
    """
    row = monitor.classify(target("ecoliderazgo"), qualified, today)
    assert row["state"] == "future_detected", row
    assert row["future_candidates"][0]["date"] == "2026-08-27"
    assert row["verified_inactive"] is False

    unknown_origin = """
    <h2>Nuestras próximas actividades</h2>
    <p>27 de agosto de 2026. Trekking Parque Nacional La Campana - Sector Ocoa.</p>
    <h2>El Equipo de EcoLiderazgo</h2>
    """
    row = monitor.classify(target("ecoliderazgo"), unknown_origin, today)
    assert row["state"] == "future_unqualified_geography", row
    assert row["future_candidates"] == []
    assert row["future_candidates_unqualified_geography"][0]["date"] == "2026-08-27"
    assert row["verified_inactive"] is False


def test_ecoliderazgo_origin_policy_allows_destination_outside_region() -> None:
    today = date(2026, 8, 18)
    markup = """
    <h2>Nuestras próximas actividades</h2>
    <p>Salida 29 de agosto de 2026 desde Valparaíso con destino al Cajón del Maipo.</p>
    <h2>El Equipo de EcoLiderazgo</h2>
    """
    row = monitor.classify(target("ecoliderazgo"), markup, today)
    assert row["state"] == "future_detected", row
    assert row["future_candidates"][0]["date"] == "2026-08-29"


def main() -> None:
    test_ipa_past_and_future()
    test_la_peste_requires_explicit_empty_or_future_date()
    test_ecoliderazgo_upcoming_catalog_without_dates_is_verified_zero()
    test_ecoliderazgo_requires_local_departure_not_destination()
    test_ecoliderazgo_origin_policy_allows_destination_outside_region()
    print("PRIORITY_ZERO_MONITORS_TESTS_OK")


if __name__ == "__main__":
    main()
