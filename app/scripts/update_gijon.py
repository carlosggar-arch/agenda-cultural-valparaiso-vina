from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

# Publication-side normalization helper kept in parity with agenda-cultural-core.
# The old JSON machine feed is intentionally no longer used: the municipal XHTML
# resource is the operational source of truth for the preview pipeline.
SOURCE_URL = "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML"
TIMEZONE = "Europe/Madrid"
MADRID = ZoneInfo(TIMEZONE)
PLACEHOLDER_TIMES = {"00:00", "23:59"}

CATEGORY_MAP = (
    ("cine", ("cine", "Cine")),
    ("audiovisual", ("cine", "Cine")),
    ("música", ("musica", "Música")),
    ("musica", ("musica", "Música")),
    ("piano", ("musica", "Música")),
    ("teatro", ("teatro", "Teatro")),
    ("artes escénicas", ("teatro", "Teatro")),
    ("exposición", ("exposiciones", "Exposiciones")),
    ("fotografía", ("exposiciones", "Exposiciones")),
    ("museo", ("museos", "Museos")),
    ("arqueo", ("museos", "Museos")),
    ("formación", ("cursos-talleres", "Cursos y talleres")),
    ("taller", ("cursos-talleres", "Cursos y talleres")),
)


def clean(value: object) -> str:
    return html.unescape(str(value or "")).strip()


def fetch_events(url: str = SOURCE_URL) -> list[dict]:
    """Compatibility entry point: read the current XHTML feed, never the stale JSON feed."""
    # Import lazily to avoid a module cycle: fetch_gijon_xhtml imports build_dataset
    # from this module as its normalization base.
    from fetch_gijon_xhtml import fetch_rows

    return fetch_rows(url)


def date_bounds(item: dict) -> tuple[str | None, str | None]:
    values = re.findall(r"\d{4}-\d{2}-\d{2}", clean(item.get("fechas")))
    if not values:
        values = re.findall(r"\d{4}-\d{2}-\d{2}", clean(item.get("fecha_inicio")))
    return (values[0], values[-1]) if values else (None, None)


def real_time(value: object) -> str | None:
    clock = clean(value)
    if not re.fullmatch(r"\d{2}:\d{2}", clock) or clock in PLACEHOLDER_TIMES:
        return None
    return clock


def timestamp(date_value: str, time_value: object) -> str:
    clock = real_time(time_value)
    if not clock:
        return date_value
    local = datetime.fromisoformat(f"{date_value}T{clock}:00").replace(tzinfo=MADRID)
    return local.isoformat(timespec="seconds")


def schedule_display(start_date: str, end_date: str, time_value: object) -> str:
    clock = real_time(time_value)
    if clock:
        return f"{start_date} · {clock}"
    if end_date != start_date:
        return f"{start_date} – {end_date}"
    return start_date


def category(item: dict) -> tuple[str, str]:
    text = " ".join([clean(item.get("tipo")), clean(item.get("etiquetas")), clean(item.get("titulo"))]).lower()
    for needle, value in CATEGORY_MAP:
        if needle in text:
            return value
    return "cultura", "Cultura"


def registration_url(item: dict) -> str | None:
    markup = clean(item.get("field_boton_asistencia_registro_"))
    match = re.search(r'href=["\']([^"\']+)', markup, flags=re.I)
    return html.unescape(match.group(1)) if match else None


def normalize_event(item: dict) -> dict | None:
    if clean(item.get("materia")).casefold() != "cultural":
        return None

    title = clean(item.get("titulo"))
    state = clean(item.get("field_estado_del_evento"))
    if not title or "cancelado" in title.casefold() or "cancelado" in state.casefold():
        return None

    start_date, end_date = date_bounds(item)
    if not start_date:
        return None
    end_date = end_date or start_date

    category_id, category_label = category(item)
    source_id = clean(item.get("id"))
    digest = hashlib.sha1(f"{source_id}|{start_date}|{title}".encode("utf-8")).hexdigest()[:16]
    official = clean(item.get("alias")) or SOURCE_URL
    registration = registration_url(item)
    venue = clean(item.get("titulo_directorio")) or clean(item.get("field_lo_name")) or "Gijón/Xixón"
    address = clean(item.get("direccion_directorio")) or clean(item.get("field_lo_address")) or None
    tags = [tag.strip() for tag in clean(item.get("etiquetas")).split(",") if tag.strip()]
    is_program = "super evento" in " ".join(tags).casefold()

    return {
        "id": f"agenda_gijon_{digest}",
        "title": title,
        "event_type": "program" if is_program else "event",
        "primary_category": {"id": category_id, "label": category_label},
        "categories": [{"id": category_id, "label": category_label}],
        "schedule": {
            "mode": "multi_day" if end_date != start_date else "single",
            "start": timestamp(start_date, item.get("hora_inicio")),
            "end": timestamp(end_date, item.get("hora_fin")) if end_date == start_date else end_date,
            "timezone": TIMEZONE,
            "display_text": schedule_display(start_date, end_date, item.get("hora_inicio")),
            "occurrences": [],
        },
        "location": {
            "venue_id": clean(item.get("localizaciones")) or None,
            "city": "Gijón",
            "commune": "Gijón/Xixón",
            "venue": venue,
            "address": address,
            "online": False,
            "latitude": None,
            "longitude": None,
        },
        "price": {
            "is_free": None,
            "currency": "EUR",
            "min_amount": None,
            "max_amount": None,
            "display_text": "Consultar condiciones",
        },
        "links": {"official": official, "tickets": None, "registration": registration, "source": official},
        "organizer": clean(item.get("organismo")) or "Ayuntamiento de Gijón/Xixón",
        "source_name": "Open Data Ayuntamiento de Gijón/Xixón",
        "source_url": SOURCE_URL,
        "last_verified_at": None,
        "public_status": {
            "source_official": True,
            "last_verified_at": None,
            "registration_open": True if registration else None,
            "registration_closed": None,
            "cancelled": False,
            "sold_out": None,
            "price_stage": None,
            "price_confirmed": False,
            "information_completeness": "partial",
            "advisory_text": "Confirma precio y condiciones en la fuente oficial.",
        },
        "description": clean(item.get("programa")) or "Actividad publicada en la Agenda de Eventos del Ayuntamiento de Gijón/Xixón.",
        "tags": tags,
        "audience": clean(item.get("tipo_publico")) or None,
        "registration_requirements": None,
        "image": {"url": clean(item.get("imagen")) or None, "alt": clean(item.get("thumbnail__alt")) or None},
    }


def build_dataset(items: list[dict], look_ahead_days: int = 14) -> dict:
    reference = datetime.now(MADRID).date()
    first_ordinal = reference.toordinal()
    last_ordinal = first_ordinal + look_ahead_days
    events: list[dict] = []

    for item in items:
        event = normalize_event(item)
        if not event:
            continue
        try:
            start_day = date.fromisoformat(str(event["schedule"]["start"])[:10])
            end_day = date.fromisoformat(str(event["schedule"]["end"] or event["schedule"]["start"])[:10])
        except ValueError:
            continue
        if end_day.toordinal() < first_ordinal or start_day.toordinal() > last_ordinal:
            continue
        events.append(event)

    events.sort(key=lambda event: (str(event["schedule"]["start"]), event["title"]))
    now = datetime.now(MADRID).isoformat(timespec="seconds")
    for event in events:
        event["last_verified_at"] = now
        event["public_status"]["last_verified_at"] = now

    return {
        "schema_version": "1.2.0",
        "generated_at": now,
        "publication_date": reference.isoformat(),
        "timezone": TIMEZONE,
        "counts": {
            "total": len(events),
            "events": sum(event["event_type"] == "event" for event in events),
            "courses": sum(event["event_type"] == "course" for event in events),
            "flexible_offers": sum(event["event_type"] == "flexible_offer" for event in events),
            "programs": sum(event["event_type"] == "program" for event in events),
        },
        "events": events,
    }


def main() -> None:
    """Keep the historical CLI name but execute the validated XHTML/editorial pipeline."""
    from fetch_gijon_xhtml import main as xhtml_main

    xhtml_main()


if __name__ == "__main__":
    main()
