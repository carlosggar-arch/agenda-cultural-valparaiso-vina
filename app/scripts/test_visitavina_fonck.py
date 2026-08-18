from __future__ import annotations

from datetime import date

from refresh_visitavina_fonck import (
    ical_occurrences,
    parse,
    query_occurrences,
    visible_list_occurrences,
)


def test_occurrence_query_dates_are_explicit() -> None:
    markup = """
    <html><body>
      <h1>Taller de Lengua Rapanui</h1>
      <a href="/actividad/taller-de-lengua-rapanui-2/?occurrence=2026-08-12">12</a>
      <a href="/actividad/taller-de-lengua-rapanui-2/?occurrence=2026-08-19">19</a>
    </body></html>
    """
    parser = parse(markup)
    assert query_occurrences(markup, parser) == {date(2026, 8, 12), date(2026, 8, 19)}


def test_visible_span_recovers_all_explicit_sessions() -> None:
    markup = """
    <html><body><h1>Taller de Lengua Rapanui</h1>
    <p>El taller de lengua rapanui contempla sesiones los miércoles 22 y 29 de julio; y 5, 12 y 19 de agosto de 2026.</p>
    <p>Lugar: Museo Fonck.</p></body></html>
    """
    values = visible_list_occurrences(parse(markup))
    assert date(2026, 7, 22) in values
    assert date(2026, 7, 29) in values
    assert date(2026, 8, 5) in values
    assert date(2026, 8, 12) in values
    assert date(2026, 8, 19) in values


def test_weekly_ical_recurrence_expands_without_guessing() -> None:
    ical = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260722T160000
RRULE:FREQ=WEEKLY;COUNT=5
END:VEVENT
END:VCALENDAR
"""
    values = ical_occurrences(ical, date(2026, 8, 18))
    assert values == {
        date(2026, 7, 22), date(2026, 7, 29), date(2026, 8, 5),
        date(2026, 8, 12), date(2026, 8, 19),
    }


def test_past_start_alone_does_not_create_future_occurrence() -> None:
    markup = """
    <html><body><h1>Taller de Lengua Rapanui</h1>
    <p>Fecha 05-agosto-2026.</p><p>Lugar: Museo Fonck.</p>
    </body></html>
    """
    parser = parse(markup)
    assert query_occurrences(markup, parser) == set()
    assert visible_list_occurrences(parser) == set()


def main() -> None:
    test_occurrence_query_dates_are_explicit()
    test_visible_span_recovers_all_explicit_sessions()
    test_weekly_ical_recurrence_expands_without_guessing()
    test_past_start_alone_does_not_create_future_occurrence()
    print("VISITAVINA_FONCK_TESTS_OK")


if __name__ == "__main__":
    main()
