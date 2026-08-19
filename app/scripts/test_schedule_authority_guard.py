from __future__ import annotations

from datetime import date

import schedule_authority_guard as guard


def event(title: str, url: str, start: str, *, source_id: str, end=None) -> dict:
    return {
        "id": title.casefold().replace(" ", "-"),
        "title": title,
        "event_type": "event",
        "source_id": source_id,
        "source_name": "Fuente",
        "source_url": url,
        "links": {"official": url, "source": url, "tickets": None},
        "schedule": {
            "mode": "dated",
            "start": start,
            "end": end,
            "timezone": "America/Santiago",
            "display_text": start,
            "occurrences": [],
        },
        "location": {"city": "Valparaíso", "venue": "Sala"},
    }


def scd_markup() -> str:
    return '''<html><body>
      <h1>ALMA PAJARÁ</h1>
      <p>DATOS PRÁCTICOS:</p>
      <p>Hora de Apertura de Puertas: 18:20</p>
      <p>Hora aprox. de inicio del show: 19:00</p>
      <p>Hora aprox. de término del evento: 20:10</p>
      <div>Fecha</div><div>Ago 20 2026</div>
      <div>Hora</div><div>7:00 pm - 9:00 pm</div>
      <div>Localización</div><div>Teatro Mauri SCD</div>
    </body></html>'''


def valpo_markup(start: str, end: str | None = None) -> str:
    end_field = f',"endDate":"{end}"' if end else ""
    return f'''<html><body><script type="application/ld+json">{{
      "@context":"https://schema.org","@type":"Event",
      "name":"Casa de la Cultura de Valparaíso – Luciana Jury en Chile",
      "startDate":"{start}"{end_field}
    }}</script></body></html>'''


def usm_markup(start: str = "19:00", end: str = "20:30") -> str:
    return f'''<html><body>
      <h1>Gala Lírica: Ópera y Canción con Christian Senn y Tabita Martínez</h1>
      <h3>Detalles del Evento</h3>
      <div>Fecha:</div><div>29/08/2026</div>
      <div>Hora inicio:</div><div>{start}</div>
      <div>Hora término:</div><div>{end}</div>
      <div>Modalidad:</div><div>Presencial</div>
      <div>Recinto:</div><div>Teatro Aula Magna</div>
    </body></html>'''


def test_scd_uses_formal_range_and_ignores_auxiliary_clocks() -> None:
    item = event(
        "Alma Pajará",
        "https://salasscd.cl/sitio/events/alma-pajara/",
        "2026-08-20T19:00:00-04:00",
        source_id="teatro_mauri_scd",
    )
    item["schedule"]["display_text"] = "2026-08-20 · 19:00, 21:00, 18:20, 20:10"
    fields = guard.apply_authority(item, scd_markup())
    assert item["schedule"]["start"] == "2026-08-20T19:00:00-04:00"
    assert item["schedule"]["end"] == "2026-08-20T21:00:00-04:00"
    assert item["schedule"]["display_text"] == "20-08-2026 · 19:00–21:00"
    assert item["schedule"]["start_confidence"] == "official_visible_schedule"
    assert "end" in fields
    assert "18:20" not in item["schedule"]["display_text"]
    assert "20:10" not in item["schedule"]["display_text"]


def test_scd_does_not_promote_practical_times_without_formal_hour_block() -> None:
    markup = '''<p>Hora de Apertura de Puertas: 18:20</p>
    <p>Hora aprox. de inicio del show: 19:00</p><p>Hora aprox. de término: 20:10</p>'''
    assert guard.salas_scd_formal_range(markup) is None


def test_valpocultura_preserves_explicit_jsonld_time() -> None:
    item = event(
        "Luciana Jury en Chile",
        "https://valpocultura.cl/evento/casa-de-la-cultura-de-valparaiso-luciana-jury-en-chile/",
        "2026-08-28",
        source_id="valpocultura",
        end="2026-08-28",
    )
    fields = guard.apply_authority(item, valpo_markup("2026-08-28T20:30:00-04:00"))
    assert item["schedule"]["start"] == "2026-08-28T20:30:00-04:00"
    assert item["schedule"]["end"] == "2026-08-28"
    assert item["schedule"]["display_text"] == "28-08-2026 · 20:30"
    assert item["schedule"]["start_confidence"] == "official_structured_schedule"
    assert "start" in fields


def test_valpocultura_never_invents_time_from_date_only_jsonld() -> None:
    item = event(
        "Evento sin hora",
        "https://valpocultura.cl/evento/evento-sin-hora/",
        "2026-08-29",
        source_id="valpocultura",
        end="2026-08-29",
    )
    assert guard.apply_authority(item, valpo_markup("2026-08-29")) == []
    assert item["schedule"]["start"] == "2026-08-29"


def test_cultura_usm_uses_start_and_end_as_one_range() -> None:
    item = event(
        "Gala Lírica: Ópera y Canción con Christian Senn y Tabita Martínez",
        "https://cultura.usm.cl/eventos/gala-lirica-opera-y-cancion-con-christian-senn-y-tabita-martinez/",
        "2026-08-29T19:00:00-04:00",
        source_id="cultura_usm",
    )
    item["schedule"]["display_text"] = "2026-08-29 · 19:00, 20:30"
    fields = guard.apply_authority(item, usm_markup())
    assert item["schedule"]["start"] == "2026-08-29T19:00:00-04:00"
    assert item["schedule"]["end"] == "2026-08-29T20:30:00-04:00"
    assert item["schedule"]["display_text"] == "29-08-2026 · 19:00–20:30"
    assert item["schedule"]["start_confidence"] == "official_visible_schedule"
    assert item["schedule"]["end_confidence"] == "official_visible_schedule"
    assert "end" in fields
    assert ", 20:30" not in item["schedule"]["display_text"]


def test_cultura_usm_requires_both_labeled_times() -> None:
    assert guard.cultura_usm_formal_range('<div>Hora inicio:</div><div>19:00</div>') is None
    assert guard.cultura_usm_formal_range('<div>Hora término:</div><div>20:30</div>') is None


def test_build_applies_all_authorities_without_cross_talking() -> None:
    alma = event(
        "Alma Pajará",
        "https://salasscd.cl/sitio/events/alma-pajara/",
        "2026-08-20T19:00:00-04:00",
        source_id="teatro_mauri_scd",
    )
    alma["schedule"]["display_text"] = "2026-08-20 · 19:00, 21:00, 18:20, 20:10"
    luciana = event(
        "Luciana Jury en Chile",
        "https://valpocultura.cl/evento/casa-de-la-cultura-de-valparaiso-luciana-jury-en-chile/",
        "2026-08-28",
        source_id="valpocultura",
        end="2026-08-28",
    )
    gala = event(
        "Gala Lírica: Ópera y Canción con Christian Senn y Tabita Martínez",
        "https://cultura.usm.cl/eventos/gala-lirica-opera-y-cancion-con-christian-senn-y-tabita-martinez/",
        "2026-08-29T19:00:00-04:00",
        source_id="cultura_usm",
    )
    gala["schedule"]["display_text"] = "2026-08-29 · 19:00, 20:30"
    original = guard.fetch
    try:
        def fake_fetch(url: str):
            if "salasscd.cl" in url:
                return True, 200, scd_markup(), None
            if "cultura.usm.cl" in url:
                return True, 200, usm_markup(), None
            return True, 200, valpo_markup("2026-08-28T20:30:00-04:00"), None
        guard.fetch = fake_fetch
        updated, report = guard.build({"events": [alma, luciana, gala]}, date(2026, 8, 18), days=120, max_fetch=5)
    finally:
        guard.fetch = original
    assert updated["events"][0]["schedule"]["display_text"] == "20-08-2026 · 19:00–21:00"
    assert updated["events"][1]["schedule"]["display_text"] == "28-08-2026 · 20:30"
    assert updated["events"][2]["schedule"]["display_text"] == "29-08-2026 · 19:00–20:30"
    assert report["updated_events"] == 3


def main() -> None:
    test_scd_uses_formal_range_and_ignores_auxiliary_clocks()
    test_scd_does_not_promote_practical_times_without_formal_hour_block()
    test_valpocultura_preserves_explicit_jsonld_time()
    test_valpocultura_never_invents_time_from_date_only_jsonld()
    test_cultura_usm_uses_start_and_end_as_one_range()
    test_cultura_usm_requires_both_labeled_times()
    test_build_applies_all_authorities_without_cross_talking()
    print("SCHEDULE_AUTHORITY_GUARD_TESTS_OK")


if __name__ == "__main__":
    main()
