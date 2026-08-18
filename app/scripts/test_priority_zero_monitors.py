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


def main() -> None:
    test_ipa_past_and_future()
    test_la_peste_requires_explicit_empty_or_future_date()
    print("PRIORITY_ZERO_MONITORS_TESTS_OK")


if __name__ == "__main__":
    main()
