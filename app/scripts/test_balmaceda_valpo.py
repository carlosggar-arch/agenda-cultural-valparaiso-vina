from __future__ import annotations

from datetime import date

from refresh_balmaceda_valpo import as_published_day, discover_links, parse, same_block_candidates


def test_recent_valpo_future_event_is_detected() -> None:
    markup = """
    <html><head><meta property="article:published_time" content="2026-08-17T12:00:00-04:00"></head>
    <body><h1>Muestra abierta de talleres</h1>
    <p>Balmaceda Arte Joven Valparaíso invita a una muestra abierta que se realizará el viernes 21 de agosto a las 18:30 horas en BAJ Valpo, Santa Isabel 739, Cerro Alegre.</p></body></html>
    """
    parser = parse(markup)
    assert as_published_day(parser) == date(2026, 8, 17)
    rows = same_block_candidates(parser, date(2026, 8, 18))
    assert len(rows) == 1, rows
    assert rows[0][0] == date(2026, 8, 21)
    assert rows[0][2] == "18:30"


def test_historical_page_without_year_cannot_create_current_event() -> None:
    markup = """
    <html><head><meta property="article:published_time" content="2022-08-20T12:00:00-04:00"></head>
    <body><h1>Recital histórico</h1>
    <p>Balmaceda Arte Joven Valparaíso invita a un recital que se realizará el 25 de agosto a las 18:00 horas en BAJ Valpo, Cerro Alegre.</p></body></html>
    """
    assert same_block_candidates(parse(markup), date(2026, 8, 18)) == []


def test_external_or_split_footer_context_does_not_publish() -> None:
    markup = """
    <html><head><meta property="article:published_time" content="2026-08-17T12:00:00-04:00"></head>
    <body><h1>Actividad en Santiago</h1>
    <p>La actividad se realizará el 24 de agosto a las 17:00 horas en Santiago.</p>
    <footer><p>Balmaceda Arte Joven Valparaíso, Santa Isabel 739, Cerro Alegre.</p></footer></body></html>
    """
    assert same_block_candidates(parse(markup), date(2026, 8, 18)) == []


def test_cancelled_block_is_rejected() -> None:
    markup = """
    <html><head><meta property="article:published_time" content="2026-08-17T12:00:00-04:00"></head>
    <body><h1>Actividad suspendida</h1>
    <p>Balmaceda Arte Joven Valparaíso informa que se suspende la actividad que se realizará el 22 de agosto a las 18:00 en BAJ Valpo, Cerro Alegre.</p></body></html>
    """
    assert same_block_candidates(parse(markup), date(2026, 8, 18)) == []


def test_internal_content_links_only() -> None:
    markup = """
    <a href="https://www.balmacedartejoven.cl/noticias/valparaiso/actividad/">Actividad</a>
    <a href="https://www.balmacedartejoven.cl/talleres/taller-prueba/">Taller</a>
    <a href="https://example.com/noticias/otra/">Externa</a>
    <a href="https://www.balmacedartejoven.cl/contacto/">Contacto</a>
    """
    links = discover_links(markup)
    assert len(links) == 2, links
    assert all("balmacedartejoven.cl" in link for link in links)


def main() -> None:
    test_recent_valpo_future_event_is_detected()
    test_historical_page_without_year_cannot_create_current_event()
    test_external_or_split_footer_context_does_not_publish()
    test_cancelled_block_is_rejected()
    test_internal_content_links_only()
    print("BALMACEDA_VALPO_TESTS_OK")


if __name__ == "__main__":
    main()
