from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
SITE_BASE = "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina"
SITEMAP = ROOT / "sitemap.xml"

CITY_CONFIG = {
    "valparaiso": {
        "label": "Valparaíso / Viña del Mar",
        "dataset": ROOT / "agenda_web.json",
        "back_url": "../../../",
        "changes": ROOT / "agenda_changes.json",
    },
    "gijon": {
        "label": "Gijón / Xixón",
        "dataset": ROOT / "app" / "data" / "gijon" / "agenda_web.json",
        "back_url": "../../../app/?city=gijon",
        "changes": None,
    },
}

CITY_EXCLUDED_IDS = {
    "valparaiso": {"agenda_968c623b60b70d2976410175"},
    "gijon": set(),
}

MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def clean_text(value: Any) -> str:
    raw = str(value or "").replace("\\n", " ").strip()
    if "<" in raw:
        parser = _TextExtractor()
        try:
            parser.feed(raw)
            raw = " ".join(parser.parts)
        except Exception:
            raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def safe_http_url(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if re.match(r"^https?://", text, re.I) else None


def event_slug(event_id: Any) -> str:
    value = str(event_id or "").strip()
    if not value:
        raise ValueError("Every generated event page requires an event id")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError(f"Event id is not URL-safe for permanent pages: {value!r}")
    return value


def parse_temporal(value: Any) -> datetime | date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return date.fromisoformat(text)
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def generated_at(payload: dict[str, Any]) -> datetime | None:
    parsed = parse_temporal(payload.get("generated_at"))
    return parsed if isinstance(parsed, datetime) else None


def human_temporal(value: Any) -> str | None:
    parsed = parse_temporal(value)
    if parsed is None:
        return None
    if isinstance(parsed, datetime):
        return f"{parsed.day} de {MONTHS[parsed.month - 1]} de {parsed.year} · {parsed:%H:%M}"
    return f"{parsed.day} de {MONTHS[parsed.month - 1]} de {parsed.year}"


def schedule_start(event: dict[str, Any]) -> Any:
    schedule = event.get("schedule") or {}
    if schedule.get("start"):
        return schedule["start"]
    occurrences = schedule.get("occurrences") or []
    return occurrences[0].get("start") if occurrences else None


def schedule_text(event: dict[str, Any]) -> str:
    schedule = event.get("schedule") or {}
    start = schedule_start(event)
    end = schedule.get("end")
    start_text = human_temporal(start)
    end_text = human_temporal(end)
    if start_text and end_text and str(start) != str(end):
        return f"{start_text} – {end_text}"
    return start_text or str(schedule.get("display_text") or "Horario por confirmar")


def event_location(event: dict[str, Any]) -> tuple[str, str | None]:
    location = event.get("location") or {}
    if location.get("online") is True:
        return str(location.get("venue") or "Actividad en línea"), None
    venue = str(location.get("venue") or location.get("city") or "Lugar por confirmar")
    address = str(location.get("address") or "").strip() or None
    return venue, address


def price_text(event: dict[str, Any]) -> str:
    price = event.get("price") or {}
    if price.get("is_free") is True:
        return "Gratis"
    return str(price.get("display_text") or "Precio por confirmar")


def category_text(event: dict[str, Any]) -> str:
    return str(
        (event.get("primary_category") or {}).get("label")
        or ((event.get("categories") or [{}])[0].get("label"))
        or "Actividad cultural"
    )


def is_gijon_open_data(event: dict[str, Any]) -> bool:
    name = str(event.get("source_name") or "").lower()
    url = str(event.get("source_url") or (event.get("links") or {}).get("source") or "")
    return ("open data" in name and "gij" in name) or url.startswith("https://opendata.gijon.es/")


def preferred_action_url(city_id: str, event: dict[str, Any]) -> str | None:
    links = event.get("links") or {}
    candidates = ["tickets", "registration"]
    if city_id == "gijon" and is_gijon_open_data(event):
        candidates.append("source")
    else:
        candidates.extend(["official", "source"])
    for key in candidates:
        candidate = safe_http_url(links.get(key))
        if candidate:
            return candidate
    return safe_http_url(event.get("source_url"))


def page_url(city_id: str, event: dict[str, Any]) -> str:
    return f"{SITE_BASE}/evento/{city_id}/{event_slug(event.get('id'))}/"


def load_recent_changes(path: Path | None, reference: datetime | None) -> dict[str, list[dict[str, Any]]]:
    if not path or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    cutoff = reference - timedelta(days=14) if reference else None
    grouped: dict[str, list[dict[str, Any]]] = {}
    for alert in payload.get("alerts") or []:
        event_id = str(alert.get("event_id") or "")
        if not event_id:
            continue
        detected = parse_temporal(alert.get("detected_at"))
        if cutoff and isinstance(detected, datetime) and detected < cutoff:
            continue
        grouped.setdefault(event_id, []).append(alert)
    return grouped


def status_notices(event: dict[str, Any], changes: list[dict[str, Any]]) -> list[tuple[str, str]]:
    status = event.get("public_status") or {}
    notices: list[tuple[str, str]] = []
    if status.get("cancelled") is True:
        notices.append(("critical", "Actividad cancelada. Revisa la fuente oficial antes de desplazarte."))
    if status.get("sold_out") is True:
        notices.append(("important", "Entradas agotadas según la última verificación disponible."))
    if status.get("registration_closed") is True:
        notices.append(("important", "La inscripción figura como cerrada."))
    completeness = str(status.get("information_completeness") or "").strip().lower()
    if completeness and completeness != "complete":
        notices.append(("pending", "Hay información pendiente de completar o confirmar."))
    advisory = clean_text(status.get("advisory_text"))
    if advisory:
        notices.append(("advisory", advisory))
    for alert in changes[-3:]:
        message = clean_text(alert.get("message"))
        if message:
            notices.append(("change", message))
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for kind, message in notices:
        key = message.casefold()
        if key not in seen:
            seen.add(key)
            unique.append((kind, message))
    return unique


def to_ics(value: Any) -> tuple[str, str] | None:
    parsed = parse_temporal(value)
    if parsed is None:
        return None
    if isinstance(parsed, datetime):
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return "DATE-TIME", parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "DATE", parsed.strftime("%Y%m%d")


def ics_escape(value: Any) -> str:
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def build_ics(city_id: str, event: dict[str, Any], event_url: str, stamp: datetime | None) -> str | None:
    start = schedule_start(event)
    start_ics = to_ics(start)
    if not start_ics:
        return None
    end_ics = to_ics((event.get("schedule") or {}).get("end"))
    stamp = stamp or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc)
    venue, address = event_location(event)
    location = ", ".join(part for part in (venue, address) if part)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Agenda Cultural//Permanent Event//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{ics_escape(city_id)}-{ics_escape(event.get('id'))}@agenda-cultural",
        f"DTSTAMP:{stamp.strftime('%Y%m%dT%H%M%SZ')}",
    ]
    kind, value = start_ics
    lines.append(f"DTSTART;VALUE=DATE:{value}" if kind == "DATE" else f"DTSTART:{value}")
    if end_ics:
        end_kind, end_value = end_ics
        lines.append(f"DTEND;VALUE=DATE:{end_value}" if end_kind == "DATE" else f"DTEND:{end_value}")
    lines.extend([
        f"SUMMARY:{ics_escape(event.get('title') or 'Actividad cultural')}",
        f"LOCATION:{ics_escape(location)}",
        f"DESCRIPTION:{ics_escape(clean_text(event.get('description'))[:1500])}",
        f"URL:{ics_escape(preferred_action_url(city_id, event) or event_url)}",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ])
    return "\r\n".join(lines)


def google_calendar_url(event: dict[str, Any], event_url: str) -> str | None:
    start = schedule_start(event)
    start_ics = to_ics(start)
    if not start_ics:
        return None
    end_ics = to_ics((event.get("schedule") or {}).get("end"))
    start_kind, start_value = start_ics
    if end_ics:
        end_value = end_ics[1]
    elif start_kind == "DATE":
        parsed = parse_temporal(start)
        assert isinstance(parsed, date) and not isinstance(parsed, datetime)
        end_value = (parsed + timedelta(days=1)).strftime("%Y%m%d")
    else:
        parsed_dt = parse_temporal(start)
        assert isinstance(parsed_dt, datetime)
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
        end_value = (parsed_dt.astimezone(timezone.utc) + timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ")
    venue, address = event_location(event)
    params = {
        "action": "TEMPLATE",
        "text": str(event.get("title") or "Actividad cultural"),
        "dates": f"{start_value}/{end_value}",
        "details": f"{clean_text(event.get('description'))[:900]}\n\n{event_url}".strip(),
        "location": ", ".join(part for part in (venue, address) if part),
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def structured_event(city_id: str, event: dict[str, Any], event_url: str) -> dict[str, Any]:
    location = event.get("location") or {}
    links = event.get("links") or {}
    status = event.get("public_status") or {}
    venue, address = event_location(event)
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": str(event.get("title") or "Actividad cultural"),
        "url": event_url,
        "description": clean_text(event.get("description"))[:3000],
        "eventStatus": (
            "https://schema.org/EventCancelled"
            if status.get("cancelled") is True
            else "https://schema.org/EventScheduled"
        ),
        "eventAttendanceMode": (
            "https://schema.org/OnlineEventAttendanceMode"
            if location.get("online") is True
            else "https://schema.org/OfflineEventAttendanceMode"
        ),
    }
    start = schedule_start(event)
    if start:
        data["startDate"] = start
    if (event.get("schedule") or {}).get("end"):
        data["endDate"] = event["schedule"]["end"]
    image = safe_http_url((event.get("image") or {}).get("url"))
    if image:
        data["image"] = [image]
    if location.get("online") is True:
        data["location"] = {"@type": "VirtualLocation", "url": preferred_action_url(city_id, event) or event_url}
    else:
        place: dict[str, Any] = {"@type": "Place", "name": venue}
        if address or location.get("city"):
            place["address"] = {
                "@type": "PostalAddress",
                "streetAddress": address or "",
                "addressLocality": str(location.get("city") or location.get("commune") or ""),
                "addressCountry": "CL" if city_id == "valparaiso" else "ES",
            }
        data["location"] = place
    organizer = str(event.get("organizer") or event.get("source_name") or "").strip()
    if organizer:
        organization: dict[str, Any] = {"@type": "Organization", "name": organizer}
        org_url = safe_http_url(event.get("source_url") or links.get("source"))
        if org_url:
            organization["url"] = org_url
        data["organizer"] = organization
    price = event.get("price") or {}
    offer: dict[str, Any] = {
        "@type": "Offer",
        "url": preferred_action_url(city_id, event) or event_url,
        "availability": (
            "https://schema.org/SoldOut"
            if status.get("sold_out") is True
            else "https://schema.org/InStock"
        ),
    }
    if price.get("is_free") is True:
        offer["price"] = 0
    elif price.get("min_amount") is not None:
        offer["price"] = price.get("min_amount")
    if price.get("currency"):
        offer["priceCurrency"] = price.get("currency")
    data["offers"] = offer
    return data


def description_meta(event: dict[str, Any], city_label: str) -> str:
    description = clean_text(event.get("description"))
    if not description:
        venue, _ = event_location(event)
        description = f"{event.get('title') or 'Actividad cultural'} · {schedule_text(event)} · {venue}."
    suffix = f" Agenda Cultural {city_label}."
    limit = max(40, 158 - len(suffix))
    if len(description) > limit:
        description = description[: limit - 1].rstrip(" ,.;:") + "…"
    return description + suffix


def render_notices(notices: list[tuple[str, str]]) -> str:
    if not notices:
        return ""
    items = "".join(
        f'<li class="event-notice event-notice--{html.escape(kind)}">{html.escape(message)}</li>'
        for kind, message in notices
    )
    return f'<section class="event-notices" aria-labelledby="avisos-title"><h2 id="avisos-title">Avisos importantes</h2><ul>{items}</ul></section>'


def render_page(
    city_id: str,
    city: dict[str, Any],
    event: dict[str, Any],
    changes: list[dict[str, Any]],
    stamp: datetime | None,
) -> tuple[str, str | None]:
    title = str(event.get("title") or "Actividad cultural").strip()
    event_url = page_url(city_id, event)
    venue, address = event_location(event)
    schedule = schedule_text(event)
    price = price_text(event)
    category = category_text(event)
    description = clean_text(event.get("description"))
    organizer = str(event.get("organizer") or "").strip()
    source_name = str(event.get("source_name") or "").strip()
    links = event.get("links") or {}
    source_url = safe_http_url(event.get("source_url") or links.get("source"))
    tickets = safe_http_url(links.get("tickets"))
    registration = safe_http_url(links.get("registration"))
    official = safe_http_url(links.get("official"))
    gijon_open_data = city_id == "gijon" and is_gijon_open_data(event)
    image = safe_http_url((event.get("image") or {}).get("url"))
    notices = status_notices(event, changes)
    status = event.get("public_status") or {}
    verified = human_temporal(status.get("last_verified_at") or event.get("last_verified_at"))
    ics = build_ics(city_id, event, event_url, stamp)
    google = google_calendar_url(event, event_url)
    whatsapp = "https://wa.me/?" + urlencode({"text": f"{title} · {schedule}\n{event_url}"})

    actions: list[str] = []
    if tickets:
        actions.append(f'<a class="event-action event-action--primary" href="{html.escape(tickets, quote=True)}" target="_blank" rel="noopener noreferrer">Entradas ↗</a>')
    if registration and registration != tickets:
        actions.append(f'<a class="event-action event-action--primary" href="{html.escape(registration, quote=True)}" target="_blank" rel="noopener noreferrer">Inscripción ↗</a>')
    if ics:
        actions.append('<a class="event-action" href="evento.ics" download>Añadir al calendario</a>')
    if google:
        actions.append(f'<a class="event-action" href="{html.escape(google, quote=True)}" target="_blank" rel="noopener noreferrer">Google Calendar ↗</a>')
    if gijon_open_data:
        if source_url and source_url not in {tickets, registration}:
            actions.append(f'<a class="event-action" href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer">Open Data oficial ↗</a>')
    elif official and official not in {tickets, registration}:
        actions.append(f'<a class="event-action" href="{html.escape(official, quote=True)}" target="_blank" rel="noopener noreferrer">Fuente oficial ↗</a>')
    elif source_url and source_url not in {tickets, registration}:
        actions.append(f'<a class="event-action" href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer">Fuente de datos ↗</a>')

    facts = [f'<div><dt>Lugar</dt><dd>{html.escape(venue)}</dd></div>']
    if address:
        facts.append(f'<div><dt>Dirección</dt><dd>{html.escape(address)}</dd></div>')
    facts.append(f'<div><dt>Fecha y horario</dt><dd>{html.escape(schedule)}</dd></div>')
    facts.append(f'<div><dt>Precio</dt><dd>{html.escape(price)}</dd></div>')
    if organizer:
        facts.append(f'<div><dt>Organiza</dt><dd>{html.escape(organizer)}</dd></div>')
    if source_name:
        label = html.escape(source_name)
        if source_url:
            label = f'<a href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer">{label} ↗</a>'
        facts.append(f'<div><dt>Fuente</dt><dd>{label}</dd></div>')
    if event.get("audience"):
        facts.append(f'<div><dt>Público</dt><dd>{html.escape(str(event.get("audience")))}</dd></div>')

    description_html = (
        f'<section class="event-description"><h2>Sobre la actividad</h2><p>{html.escape(description)}</p></section>'
        if description else ""
    )
    image_html = (
        f'<figure class="event-hero-media"><img src="{html.escape(image, quote=True)}" alt="{html.escape(str((event.get("image") or {}).get("alt") or title), quote=True)}" loading="eager" decoding="async"></figure>'
        if image
        else f'<div class="event-hero-fallback" role="img" aria-label="Actividad de {html.escape(category)}"><span>✦</span><strong>{html.escape(category)}</strong></div>'
    )
    notices_html = render_notices(notices)
    verified_html = f'<p class="event-verified">Última verificación: {html.escape(verified)}</p>' if verified else ""
    meta = description_meta(event, city["label"])
    ld = json.dumps(structured_event(city_id, event, event_url), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    og_image = f'<meta property="og:image" content="{html.escape(image, quote=True)}">' if image else ""

    page = f'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(title)} · Agenda Cultural</title>
  <meta name="description" content="{html.escape(meta, quote=True)}">
  <link rel="canonical" href="{html.escape(event_url, quote=True)}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{html.escape(title, quote=True)}">
  <meta property="og:description" content="{html.escape(meta, quote=True)}">
  <meta property="og:url" content="{html.escape(event_url, quote=True)}">
  {og_image}
  <meta name="twitter:card" content="summary_large_image">
  <link rel="stylesheet" href="../../../assets/event-page.css?v=20260817">
  <script type="application/ld+json">{ld}</script>
</head>
<body data-event-page data-event-id="{html.escape(str(event.get('id')), quote=True)}" data-city="{html.escape(city_id, quote=True)}">
  <header class="event-site-header"><a href="{html.escape(city['back_url'], quote=True)}" class="event-brand"><span aria-hidden="true">✦</span><strong>Agenda Cultural</strong><small>{html.escape(city['label'])}</small></a></header>
  <main class="event-page">
    <nav class="event-breadcrumb" aria-label="Navegación"><a href="{html.escape(city['back_url'], quote=True)}">← Volver a la agenda</a></nav>
    <article class="event-sheet">
      {image_html}
      <div class="event-main">
        <p class="event-kicker">{html.escape(category)}</p>
        <h1>{html.escape(title)}</h1>
        {notices_html}
        <dl class="event-facts">{''.join(facts)}</dl>
        <div class="event-actions">{''.join(actions)}</div>
        <div class="event-share" aria-label="Compartir evento">
          <a class="event-action" href="{html.escape(whatsapp, quote=True)}" target="_blank" rel="noopener noreferrer">WhatsApp ↗</a>
          <button class="event-action" type="button" data-native-share>Compartir</button>
          <button class="event-action" type="button" data-copy-link>Copiar enlace</button>
          <span class="event-share-status" data-share-status aria-live="polite"></span>
        </div>
        {description_html}
        {verified_html}
        <p class="event-source-note">La Agenda Cultural reúne información procedente de fuentes verificables. Confirma cualquier cambio de última hora con el organizador antes de asistir.</p>
      </div>
    </article>
  </main>
  <script src="../../../assets/usage-analytics.js?v=20260817-stage32" defer></script>
  <script src="../../../assets/event-page.js?v=20260817" defer></script>
</body>
</html>
'''
    return page, ics


def static_sitemap_urls() -> list[str]:
    return [
        f"{SITE_BASE}/",
        f"{SITE_BASE}/app/",
        f"{SITE_BASE}/fuentes.html",
        f"{SITE_BASE}/proponer-evento.html",
        f"{SITE_BASE}/registrar-organizacion.html",
    ]


def render_sitemap(event_urls: list[str]) -> str:
    rows = []
    for url in static_sitemap_urls():
        rows.append(f"  <url>\n    <loc>{xml_escape(url)}</loc>\n    <changefreq>weekly</changefreq>\n  </url>")
    for url in sorted(set(event_urls)):
        rows.append(f"  <url>\n    <loc>{xml_escape(url)}</loc>\n    <changefreq>daily</changefreq>\n  </url>")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"


def generate(*, check: bool = False) -> dict[str, int]:
    for required in ("assets/event-page.css", "assets/event-page.js"):
        if not (ROOT / required).exists():
            raise SystemExit(f"{required} is required")

    counts: dict[str, int] = {}
    event_urls: list[str] = []
    paths: set[str] = set()

    for city_id, city in CITY_CONFIG.items():
        dataset_path: Path = city["dataset"]
        if not dataset_path.exists():
            raise SystemExit(f"Missing city dataset: {dataset_path}")
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        events = payload.get("events") or []
        if not isinstance(events, list):
            raise SystemExit(f"Invalid events array: {dataset_path}")
        stamp = generated_at(payload)
        changes = load_recent_changes(city.get("changes"), stamp)
        excluded = CITY_EXCLUDED_IDS.get(city_id, set())
        current = [event for event in events if isinstance(event, dict) and str(event.get("id") or "") not in excluded]
        counts[city_id] = len(current)

        for event in current:
            slug = event_slug(event.get("id"))
            relative = f"evento/{city_id}/{slug}"
            if relative in paths:
                raise SystemExit(f"Duplicate generated event path: {relative}")
            paths.add(relative)
            event_url = page_url(city_id, event)
            page, ics = render_page(city_id, city, event, changes.get(str(event.get("id")), []), stamp)
            for required in ("<h1>", "application/ld+json", 'rel="canonical"', "Copiar enlace", "Agenda Cultural"):
                if required not in page:
                    raise SystemExit(f"Generated page missing {required}: {relative}")
            event_urls.append(event_url)
            if not check:
                directory = ROOT / relative
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "index.html").write_text(page, encoding="utf-8")
                if ics:
                    (directory / "evento.ics").write_text(ics, encoding="utf-8", newline="")

    if check:
        if len(event_urls) != sum(counts.values()):
            raise SystemExit("Event URL count does not match generated event count")
    else:
        SITEMAP.write_text(render_sitemap(event_urls), encoding="utf-8")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate permanent static event pages from public city datasets.")
    parser.add_argument("--check", action="store_true", help="Validate all pages in memory without writing files.")
    args = parser.parse_args()
    counts = generate(check=args.check)
    total = sum(counts.values())
    mode = "VALIDATED" if args.check else "GENERATED"
    breakdown = ", ".join(f"{city}={count}" for city, count in counts.items())
    print(f"EVENT_PAGES_{mode} total={total} {breakdown}")


if __name__ == "__main__":
    main()
