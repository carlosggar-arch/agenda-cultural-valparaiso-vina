from __future__ import annotations

from datetime import date

from refresh_visitavina_fonck import event_clock, listing_occurrences, parse, title_ok, venue_ok


def test_exact_event_slug_occurrences_only() -> None:
    markup = """
    <html><body>
      <a href="/actividad/taller-de-lengua-rapanui-2/?occurrence=2026-08-12&time=1">Rapanui 12</a>
      <a href="https://visitavina.munivina.cl/actividad/taller-de-lengua-rapanui-2/?occurrence=2026-08-19&time=2">Rapanui 19</a>
      <a href="/actividad/otro-evento/?occurrence=2026-08-22">Otro</a>
      <a href="https://example.com/actividad/taller-de-lengua-rapanui-2/?occurrence=2026-08-25">Externo</a>
    </body></html>
    """
    values = listing_occurrences(markup)
    assert set(values) == {date(2026, 8, 12), date(2026, 8, 19)}, values
    assert "occurrence=2026-08-19" in values[date(2026, 8, 19)]


def test_past_detail_date_alone_does_not_create_occurrence() -> None:
    markup = """
    <html><body><h1>Taller // Lengua Rapanui</h1>
    <p>Fecha 12-agosto-2026.</p><p>Lugar: Museo Fonck.</p>
    </body></html>
    """
    assert listing_occurrences(markup) == {}


def test_official_title_variant_and_venue_are_accepted() -> None:
    markup = """
    <html><body><h1>Taller // Lengua Rapanui</h1>
    <p>El taller busca promover el aprendizaje de la lengua rapanui.</p>
    <p>Museo Fonck</p></body></html>
    """
    parser = parse(markup)
    assert title_ok(parser.h1)
    assert venue_ok(parser)


def test_event_specific_pm_time_wins_over_generic_opening_hours() -> None:
    markup = """
    <html><body>
    <p>Hora Sábado y Domingo de 10:00 a 14:00 y de 15:00 a 17:30 horas</p>
    <p>4:00 pm - 5:30 pm</p>
    <h1>Taller // Lengua Rapanui</h1><p>Museo Fonck</p>
    </body></html>
    """
    assert event_clock(parse(markup)) == "16:00"


def main() -> None:
    test_exact_event_slug_occurrences_only()
    test_past_detail_date_alone_does_not_create_occurrence()
    test_official_title_variant_and_venue_are_accepted()
    test_event_specific_pm_time_wins_over_generic_opening_hours()
    print("VISITAVINA_FONCK_TESTS_OK")


if __name__ == "__main__":
    main()
