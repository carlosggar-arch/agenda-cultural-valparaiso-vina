from __future__ import annotations

from datetime import date

from refresh_museo_maritimo import extract_events_from_article, monthly_program_items


def test_month_only_programme_is_detected_but_not_published() -> None:
    today = date(2026, 8, 18)
    rows = [
        "PROGRAMACIÓN",
        "Agosto",
        'EXPOSICIÓN TEMPORAL "Un mar de Juegos"',
        "Agosto",
        'EXPOSICIÓN TEMPORAL DIGITAL "Prat en el corazón de Chile"',
    ]
    items = monthly_program_items(rows, today)
    assert len(items) == 2, items
    assert all(item["publishable"] is False for item in items)
    assert all(item["reason"] == "month_only_no_explicit_start_end" for item in items)


def test_explicit_future_official_event_is_publishable() -> None:
    today = date(2026, 8, 18)
    markup = """
    <html><head><meta property="og:image" content="https://museomaritimo.cl/evento.jpg"></head>
    <body><h1>Jornada familiar de prueba</h1>
    <p>El sábado 22 de agosto de 2026, entre las 10:00 y las 17:00 horas, el Museo Marítimo Nacional
    realizará una jornada familiar en dependencias del Museo Marítimo Nacional, Paseo 21 de Mayo 45,
    cerro Artillería, Valparaíso. La actividad tendrá entrada liberada.</p>
    <p>En caso de lluvia, la actividad será suspendida y se informará en redes oficiales.</p></body></html>
    """
    events = extract_events_from_article(markup, "https://museomaritimo.cl/2026/08/18/jornada-prueba/", today)
    assert len(events) == 1, events
    item = events[0]
    assert item["title"] == "Jornada familiar de prueba"
    assert item["schedule"]["start"].startswith("2026-08-22T10:00:00")
    assert item["location"]["city"] == "Valparaíso"
    assert item["location"]["venue"] == "Museo Marítimo Nacional"
    assert item["price"]["is_free"] is True
    assert item["links"]["official"].endswith("/jornada-prueba/")
    assert item["image"]["url"] == "https://museomaritimo.cl/evento.jpg"


def test_past_external_or_address_date_is_not_published() -> None:
    today = date(2026, 1, 15)
    past = """
    <html><body><h1>Actividad pasada</h1>
    <p>El 8 de enero de 2026 se realizó una actividad en dependencias del Museo Marítimo Nacional.</p>
    </body></html>
    """
    external = """
    <html><body><h1>Exposición itinerante</h1>
    <p>El 22 de agosto de 2026 se realizará una exposición en Iquique.</p>
    <footer>Museo Marítimo Nacional, Paseo 21 de Mayo 45, Cerro Artillería, Valparaíso.</footer>
    </body></html>
    """
    address_only = """
    <html><body><h1>Información general</h1>
    <p>Visítanos en Paseo 21 de Mayo 45, Cerro Artillería, Valparaíso.</p>
    <p>El Museo Marítimo Nacional invita a conocer sus salas.</p></body></html>
    """
    assert extract_events_from_article(past, "https://museomaritimo.cl/2026/01/09/pasada/", today) == []
    assert extract_events_from_article(external, "https://museomaritimo.cl/2026/01/15/externa/", today) == []
    assert extract_events_from_article(address_only, "https://museomaritimo.cl/2026/01/15/info/", today) == []


def test_cancelled_future_article_is_not_published() -> None:
    today = date(2026, 8, 18)
    markup = """
    <html><body><h1>Actividad suspendida</h1>
    <p>La actividad prevista para el 25 de agosto de 2026 en dependencias del Museo Marítimo Nacional fue suspendida.</p>
    </body></html>
    """
    assert extract_events_from_article(markup, "https://museomaritimo.cl/2026/08/18/suspendida/", today) == []


def main() -> None:
    test_month_only_programme_is_detected_but_not_published()
    test_explicit_future_official_event_is_publishable()
    test_past_external_or_address_date_is_not_published()
    test_cancelled_future_article_is_not_published()
    print("MUSEO_MARITIMO_TESTS_OK")


if __name__ == "__main__":
    main()
