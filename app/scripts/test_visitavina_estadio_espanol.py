from __future__ import annotations

from datetime import date

from refresh_visitavina_estadio_espanol import (
    event_times,
    listing_candidates,
    parse_detail,
    venue_ok,
)


def test_listing_shortlists_only_exact_venue_context() -> None:
    markup = """
    <html><body>
      <a href="/actividad/otro-show/?occurrence=2026-08-22">Otro show</a>
      <div>Teatro Municipal de Viña del Mar</div><div>8:00 pm</div>
      <a href="/actividad/concierto-orquesta-marga-marga-3/?occurrence=2026-08-27">Concierto // Orquesta Marga Marga</a>
      <div>Estadio Español</div><div>7:30 pm - 9:00 pm</div>
      <a href="/actividad/otro-evento/?occurrence=2026-08-29">Otro evento</a>
      <div>Palacio Rioja</div>
    </body></html>
    """
    rows = listing_candidates(markup, date(2026, 8, 18), date(2026, 10, 17))
    assert len(rows) == 1, rows
    assert rows[0]["date"] == date(2026, 8, 27)
    assert "concierto-orquesta-marga-marga-3" in rows[0]["url"]


def test_past_estadio_occurrence_is_not_republished() -> None:
    markup = """
    <a href="/actividad/humor-pasado/?occurrence=2026-08-08">Humor pasado</a>
    <div>Estadio Español</div>
    <a href="/actividad/otro/?occurrence=2026-08-20">Otro</a><div>Palacio Rioja</div>
    """
    rows = listing_candidates(markup, date(2026, 8, 18), date(2026, 10, 17))
    assert rows == []


def test_detail_confirms_venue_and_specific_time_range() -> None:
    markup = """
    <html><body>
      <h1>Concierto // Orquesta Marga Marga</h1>
      <p>Actividad musical para la comunidad.</p>
      <p>Estadio Español</p>
      <p>7:30 pm - 9:00 pm</p>
      <footer>Horario oficina 10:00 am - 5:30 pm</footer>
    </body></html>
    """
    parser = parse_detail(markup)
    assert venue_ok(parser)
    assert event_times(parser) == ("19:30", "21:00")


def test_unrelated_detail_cannot_be_published() -> None:
    markup = """
    <html><body><h1>Concierto cualquiera</h1><p>Teatro Municipal de Viña del Mar</p><p>7:30 pm</p></body></html>
    """
    parser = parse_detail(markup)
    assert not venue_ok(parser)


def main() -> None:
    test_listing_shortlists_only_exact_venue_context()
    test_past_estadio_occurrence_is_not_republished()
    test_detail_confirms_venue_and_specific_time_range()
    test_unrelated_detail_cannot_be_published()
    print("VISITAVINA_ESTADIO_ESPANOL_TESTS_OK")


if __name__ == "__main__":
    main()
