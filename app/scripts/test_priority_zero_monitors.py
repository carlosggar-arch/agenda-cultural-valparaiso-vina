from __future__ import annotations

from datetime import date

import refresh_priority_zero_monitors as monitor


def target(target_id: str) -> dict:
    return next(item for item in monitor.TARGETS if item["id"] == target_id)


def test_baj_future_detection_requires_valpo_context() -> None:
    today = date(2026, 8, 18)
    markup = """
    <article><p>Valparaíso</p><h2>Inscripciones abiertas</h2><p>Taller de fotografía</p><p>25 de agosto de 2026</p></article>
    <article><p>Metropolitana</p><h2>Taller de teatro</h2><p>30 de agosto de 2026</p></article>
    """
    row = monitor.classify(target("balmaceda_arte_joven_valpo"), markup, today)
    assert row["state"] == "future_detected"
    assert row["future_candidates_count"] >= 1
    assert any(item["date"] == "2026-08-25" for item in row["future_candidates"])


def test_baj_past_only_is_verified_zero() -> None:
    today = date(2026, 8, 18)
    markup = "<p>Valparaíso</p><h2>Talleres intensivos</h2><p>15 de julio de 2026</p>"
    row = monitor.classify(target("balmaceda_arte_joven_valpo"), markup, today)
    assert row["state"] == "verified_no_publishable_future"
    assert row["verified_inactive"] is True


def test_ipa_past_and_future() -> None:
    today = date(2026, 8, 18)
    past = "<p>Yo no nací para amar</p><p>Location : Sala Teatro Ipa Jue, julio 30, 2026 7:00 PM</p>"
    row = monitor.classify(target("sala_teatro_ipa"), past, today)
    assert row["state"] == "verified_no_publishable_future"

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
    row = monitor.classify(target("teatro_la_peste"), uncertain, today)
    assert row["state"] == "indeterminate"
    assert row["verified_inactive"] is False

    future = "<h1>Tus Entradas para Teatro La Peste</h1><p>Nueva función 2 de septiembre de 2026</p>"
    row = monitor.classify(target("teatro_la_peste"), future, today)
    assert row["state"] == "future_detected"


def main() -> None:
    test_baj_future_detection_requires_valpo_context()
    test_baj_past_only_is_verified_zero()
    test_ipa_past_and_future()
    test_la_peste_requires_explicit_empty_or_future_date()
    print("PRIORITY_ZERO_MONITORS_TESTS_OK")


if __name__ == "__main__":
    main()
