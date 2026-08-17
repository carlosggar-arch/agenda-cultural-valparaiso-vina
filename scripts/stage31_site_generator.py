from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

import generate_event_pages as base

ROOT = base.ROOT
SITE_BASE = base.SITE_BASE
SITEMAP = base.SITEMAP

CITY_SEO = {
    "valparaiso": {
        "lang": "es-CL",
        "og_locale": "es_CL",
        "country": "CL",
        "currency": "CLP",
        "canonical": f"{SITE_BASE}/",
    },
    "gijon": {
        "lang": "es-ES",
        "og_locale": "es_ES",
        "country": "ES",
        "currency": "EUR",
        "canonical": f"{SITE_BASE}/gijon/",
    },
}

EVENT_TYPES = {"event", "course", "workshop"}


def _json_ld(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type") or "event").strip().lower()


def _event_status(event: dict[str, Any]) -> tuple[str, str | None]:
    status = event.get("public_status") or {}
    previous = status.get("previous_start_date") or event.get("previous_start_date")
    if status.get("cancelled") is True:
        return "https://schema.org/EventCancelled", None
    if status.get("postponed") is True:
        return "https://schema.org/EventPostponed", None
    if status.get("rescheduled") is True or previous:
        return "https://schema.org/EventRescheduled", str(previous) if previous else None
    return "https://schema.org/EventScheduled", None


def _place_schema(city_id: str, event: dict[str, Any]) -> dict[str, Any]:
    seo = CITY_SEO[city_id]
    location = event.get("location") or {}
    venue, address = base.event_location(event)
    place: dict[str, Any] = {"@type": "Place", "name": venue}
    postal: dict[str, Any] = {"@type": "PostalAddress", "addressCountry": seo["country"]}
    if address:
        postal["streetAddress"] = address
    locality = str(location.get("city") or location.get("commune") or "").strip()
    if locality:
        postal["addressLocality"] = locality
    region = str(location.get("region") or "").strip()
    if region:
        postal["addressRegion"] = region
    postal_code = str(location.get("postal_code") or location.get("postalCode") or "").strip()
    if postal_code:
        postal["postalCode"] = postal_code
    place["address"] = postal
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if latitude is not None and longitude is not None:
        place["geo"] = {"@type": "GeoCoordinates", "latitude": latitude, "longitude": longitude}
    return place


def structured_document(city_id: str, event: dict[str, Any], event_url: str) -> dict[str, Any]:
    seo = CITY_SEO[city_id]
    event_type = _event_type(event)
    title = str(event.get("title") or "Actividad cultural").strip()
    description = base.clean_text(event.get("description"))[:3000]
    image = base.safe_http_url((event.get("image") or {}).get("url"))
    start = base.schedule_start(event)
    location = event.get("location") or {}
    organizer = str(event.get("organizer") or "").strip()
    links = event.get("links") or {}

    eligible_event = event_type in EVENT_TYPES and bool(start) and location.get("online") is not True
    if eligible_event:
        status_url, previous_start = _event_status(event)
        data: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Event",
            "@id": f"{event_url}#event",
            "name": title,
            "url": event_url,
            "startDate": start,
            "eventStatus": status_url,
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": _place_schema(city_id, event),
            "inLanguage": seo["lang"],
        }
        if description:
            data["description"] = description
        end = (event.get("schedule") or {}).get("end")
        if end:
            data["endDate"] = end
        if previous_start:
            data["previousStartDate"] = previous_start
        if image:
            data["image"] = [image]
        if organizer:
            organization: dict[str, Any] = {"@type": "Organization", "name": organizer}
            organizer_url = base.safe_http_url(links.get("official"))
            if organizer_url:
                organization["url"] = organizer_url
            data["organizer"] = organization

        price = event.get("price") or {}
        free = price.get("is_free") is True
        if price.get("is_free") is not None:
            data["isAccessibleForFree"] = free
        offer_url = base.safe_http_url(links.get("tickets")) or base.safe_http_url(links.get("registration"))
        price_value = 0 if free else price.get("min_amount")
        if offer_url and price_value is not None:
            offer: dict[str, Any] = {
                "@type": "Offer",
                "url": offer_url,
                "price": price_value,
                "priceCurrency": str(price.get("currency") or seo["currency"]),
            }
            if (event.get("public_status") or {}).get("sold_out") is True:
                offer["availability"] = "https://schema.org/SoldOut"
            else:
                offer["availability"] = "https://schema.org/InStock"
            data["offers"] = offer
        return data

    common: dict[str, Any] = {
        "@context": "https://schema.org",
        "@id": f"{event_url}#main",
        "name": title,
        "url": event_url,
        "inLanguage": seo["lang"],
    }
    if description:
        common["description"] = description
    if image:
        common["image"] = image

    if event_type == "flexible_offer":
        common["@type"] = "Service"
        locality = str(location.get("city") or location.get("commune") or "").strip()
        if locality:
            common["areaServed"] = {"@type": "City", "name": locality}
        if organizer:
            common["provider"] = {"@type": "Organization", "name": organizer}
    elif event_type == "program":
        common["@type"] = "CollectionPage"
        common["about"] = {"@type": "Thing", "name": base.category_text(event)}
    else:
        common["@type"] = "WebPage"
    return common



def breadcrumb_schema(city_id: str, event: dict[str, Any], event_url: str) -> dict[str, Any]:
    title = str(event.get("title") or "Actividad cultural").strip()
    if city_id == "gijon":
        items = [
            {"@type": "ListItem", "position": 1, "name": "¡Vivamos! · Agenda Cultural", "item": f"{SITE_BASE}/"},
            {"@type": "ListItem", "position": 2, "name": "Agenda Cultural Gijón / Xixón", "item": CITY_SEO[city_id]["canonical"]},
            {"@type": "ListItem", "position": 3, "name": title, "item": event_url},
        ]
    else:
        items = [
            {"@type": "ListItem", "position": 1, "name": "Agenda Cultural Valparaíso / Viña del Mar", "item": CITY_SEO[city_id]["canonical"]},
            {"@type": "ListItem", "position": 2, "name": title, "item": event_url},
        ]
    return {"@type": "BreadcrumbList", "itemListElement": items}


def structured_page_document(city_id: str, event: dict[str, Any], event_url: str) -> dict[str, Any]:
    primary = dict(structured_document(city_id, event, event_url))
    primary.pop("@context", None)
    return {"@context": "https://schema.org", "@graph": [primary, breadcrumb_schema(city_id, event, event_url)]}

def enhance_event_page(
    city_id: str,
    city: dict[str, Any],
    event: dict[str, Any],
    changes: list[dict[str, Any]],
    stamp: Any,
) -> tuple[str, str | None]:
    page, ics = base.render_page(city_id, city, event, changes, stamp)
    seo = CITY_SEO[city_id]
    event_url = base.page_url(city_id, event)
    title = str(event.get("title") or "Actividad cultural").strip()
    meta = base.description_meta(event, city["label"])
    image = base.safe_http_url((event.get("image") or {}).get("url"))

    structured = _json_ld(structured_page_document(city_id, event, event_url))
    page = re.sub(
        r'<script type="application/ld\+json">.*?</script>',
        f'<script type="application/ld+json">{structured}</script>',
        page,
        count=1,
        flags=re.S,
    )
    page = page.replace('<html lang="es">', f'<html lang="{seo["lang"]}">', 1)
    page = page.replace(
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n  <meta name="robots" content="index,follow,max-image-preview:large">',
        1,
    )
    page = page.replace(
        f'<title>{html.escape(title)} · Agenda Cultural</title>',
        f'<title>{html.escape(title)} · {html.escape(city["label"])} · ¡Vivamos!</title>',
        1,
    )
    page = page.replace(
        '<meta property="og:type" content="website">',
        f'<meta property="og:type" content="website">\n  <meta property="og:site_name" content="¡Vivamos! · Agenda Cultural">\n  <meta property="og:locale" content="{seo["og_locale"]}">',
        1,
    )
    twitter = (
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'  <meta name="twitter:title" content="{html.escape(title, quote=True)}">\n'
        f'  <meta name="twitter:description" content="{html.escape(meta, quote=True)}">'
    )
    if image:
        twitter += f'\n  <meta name="twitter:image" content="{html.escape(image, quote=True)}">'
    page = page.replace('<meta name="twitter:card" content="summary_large_image">', twitter, 1)
    stylesheet = '<link rel="stylesheet" href="../../../assets/event-page.css?v=20260817">'
    page = page.replace(
        stylesheet,
        stylesheet + '\n  <link rel="stylesheet" href="../../../assets/accessibility.css?v=20260817-stage31">',
        1,
    )
    body_match = re.search(r'(<body[^>]*>)', page)
    if not body_match:
        raise RuntimeError(f"Generated event page has no body: {event_url}")
    page = page[:body_match.end()] + '\n  <a class="skip-link" href="#contenido">Saltar al contenido</a>' + page[body_match.end():]
    page = page.replace('<main class="event-page">', '<main id="contenido" class="event-page" tabindex="-1">', 1)
    page = page.replace('<div class="event-actions">', '<div class="event-actions" role="group" aria-label="Acciones del evento">', 1)
    page = page.replace('<div class="event-share" aria-label="Compartir evento">', '<div class="event-share" role="group" aria-label="Compartir evento">', 1)
    return page, ics


def _lastmod(payload: dict[str, Any]) -> str | None:
    parsed = base.generated_at(payload)
    return parsed.date().isoformat() if parsed else str(payload.get("publication_date") or "").strip() or None


def render_city_landing(city_id: str, city: dict[str, Any], payload: dict[str, Any], events: list[dict[str, Any]]) -> str:
    if city_id != "gijon":
        raise ValueError("The standalone city landing is currently reserved for Gijón; Valparaíso/Viña uses the site root.")
    canonical = CITY_SEO[city_id]["canonical"]
    count = len(events)
    description = f"Agenda Cultural de Gijón / Xixón con {count} actividades actuales, revisadas desde fuentes verificables."
    event_items = []
    cards = []
    for position, event in enumerate(events, start=1):
        event_url = base.page_url(city_id, event)
        title = str(event.get("title") or "Actividad cultural").strip()
        venue, _ = base.event_location(event)
        schedule = base.schedule_text(event)
        category = base.category_text(event)
        event_items.append({"@type": "ListItem", "position": position, "url": event_url, "name": title})
        cards.append(
            '<article class="city-event-card">'
            f'<p class="city-eyebrow">{html.escape(category)}</p>'
            f'<h3><a href="../evento/gijon/{html.escape(base.event_slug(event.get("id")), quote=True)}/">{html.escape(title)}</a></h3>'
            f'<p>{html.escape(schedule)}</p>'
            f'<p class="city-event-meta">{html.escape(venue)}</p>'
            '</article>'
        )
    image = next((base.safe_http_url((event.get("image") or {}).get("url")) for event in events if base.safe_http_url((event.get("image") or {}).get("url"))), None)
    ld: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": f"{canonical}#agenda",
        "name": "Agenda Cultural Gijón / Xixón",
        "url": canonical,
        "description": description,
        "inLanguage": "es-ES",
        "spatialCoverage": {"@type": "City", "name": "Gijón / Xixón", "address": {"@type": "PostalAddress", "addressCountry": "ES"}},
        "mainEntity": {"@type": "ItemList", "numberOfItems": count, "itemListElement": event_items},
    }
    if image:
        ld["image"] = image
    landing_primary = dict(ld)
    landing_primary.pop("@context", None)
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            landing_primary,
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "¡Vivamos! · Agenda Cultural", "item": f"{SITE_BASE}/"},
                {"@type": "ListItem", "position": 2, "name": "Agenda Cultural Gijón / Xixón", "item": canonical},
            ]},
        ],
    }
    og_image = f'\n  <meta property="og:image" content="{html.escape(image, quote=True)}">' if image else ""
    return f'''<!doctype html>
<html lang="es-ES">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <title>Agenda Cultural Gijón / Xixón · ¡Vivamos!</title>
  <meta name="description" content="{html.escape(description, quote=True)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="¡Vivamos! · Agenda Cultural">
  <meta property="og:locale" content="es_ES">
  <meta property="og:title" content="Agenda Cultural Gijón / Xixón · ¡Vivamos!">
  <meta property="og:description" content="{html.escape(description, quote=True)}">
  <meta property="og:url" content="{canonical}">{og_image}
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Agenda Cultural Gijón / Xixón · ¡Vivamos!">
  <meta name="twitter:description" content="{html.escape(description, quote=True)}">
  <link rel="stylesheet" href="../assets/city-page.css?v=20260817-stage31">
  <link rel="stylesheet" href="../assets/accessibility.css?v=20260817-stage31">
  <script type="application/ld+json">{_json_ld(ld)}</script>
</head>
<body>
  <a class="skip-link" href="#contenido">Saltar al contenido</a>
  <header class="city-site-header"><div class="city-site-header-inner"><a class="city-brand" href="../">✦ <span>¡Vivamos! · Agenda Cultural</span></a><a class="city-open-app" href="../app/?city=gijon">Abrir agenda interactiva</a></div></header>
  <main id="contenido" class="city-page" tabindex="-1">
    <nav class="city-breadcrumb" aria-label="Migas de pan"><a href="../">← Valparaíso / Viña del Mar</a></nav>
    <section class="city-hero" aria-labelledby="city-title">
      <p class="city-eyebrow">Gijón / Xixón · Asturias</p>
      <h1 id="city-title">Agenda Cultural de Gijón / Xixón</h1>
      <p class="city-hero-copy">{html.escape(description)} Consulta fechas, lugares y fuentes, y abre la ficha permanente de cada actividad.</p>
      <div class="city-hero-actions"><a class="city-button" href="../app/?city=gijon">Explorar con filtros</a><a class="city-button" href="#actividades">Ver {count} actividades</a></div>
    </section>
    <section id="actividades" class="city-section" aria-labelledby="activities-title">
      <h2 id="activities-title">Actividades actuales</h2>
      <div class="city-event-grid">{''.join(cards)}</div>
    </section>
  </main>
  <footer class="city-footer"><div class="city-footer-inner"><strong>¡Vivamos!</strong><p>Agenda pública elaborada desde fuentes verificables. Confirma cambios de última hora con el organizador antes de asistir.</p></div></footer>
</body>
</html>
'''



def root_structured_document(payload: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = CITY_SEO["valparaiso"]["canonical"]
    org = f"{SITE_BASE}/#organization"
    website = f"{SITE_BASE}/#website"
    items = [{"@type": "ListItem", "position": n, "url": base.page_url("valparaiso", event), "name": str(event.get("title") or "Actividad cultural").strip()} for n, event in enumerate(events, 1)]
    collection = {
        "@type": "CollectionPage", "@id": f"{canonical}#agenda", "name": "Agenda Cultural Valparaíso / Viña del Mar", "url": canonical,
        "description": "Agenda cultural de Valparaíso y Viña del Mar con actividades revisadas desde fuentes verificables.", "inLanguage": "es-CL",
        "isPartOf": {"@id": website}, "publisher": {"@id": org},
        "spatialCoverage": [{"@type": "City", "name": "Valparaíso"}, {"@type": "City", "name": "Viña del Mar"}],
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(events), "itemListElement": items},
    }
    if payload.get("generated_at"):
        collection["dateModified"] = payload["generated_at"]
    return {"@context": "https://schema.org", "@graph": [
        {"@type": "Organization", "@id": org, "name": "¡Vivamos! · Agenda Cultural", "url": canonical},
        {"@type": "WebSite", "@id": website, "name": "¡Vivamos! · Agenda Cultural", "url": canonical, "inLanguage": "es-CL", "publisher": {"@id": org}},
        collection,
    ]}


def render_root_landing(payload: dict[str, Any], events: list[dict[str, Any]]) -> str:
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    page = page.replace('<html lang="es">', '<html lang="es-CL">', 1)
    if 'name="robots"' not in page:
        page = page.replace('<meta name="viewport" content="width=device-width,initial-scale=1">', '<meta name="viewport" content="width=device-width,initial-scale=1">\n  <meta name="robots" content="index,follow,max-image-preview:large">', 1)
    if 'assets/accessibility.css' not in page:
        page = page.replace('<link rel="stylesheet" href="./assets/agenda.css">', '<link rel="stylesheet" href="./assets/agenda.css">\n  <link rel="stylesheet" href="./assets/accessibility.css?v=20260817-stage31">', 1)
    page = page.replace('<main id="contenido">', '<main id="contenido" tabindex="-1">', 1)
    if 'property="og:site_name"' not in page:
        page = page.replace('<meta property="og:type" content="website">', '<meta property="og:type" content="website">\n  <meta property="og:site_name" content="¡Vivamos! · Agenda Cultural">', 1)
    image = f"{SITE_BASE}/assets/cerro-concepcion-valparaiso.jpg?v=20260729-corrected"
    if 'property="og:image"' not in page:
        page = page.replace(f'<meta property="og:url" content="{SITE_BASE}/">', f'<meta property="og:url" content="{SITE_BASE}/">\n  <meta property="og:image" content="{image}">', 1)
    page = page.replace('<meta name="twitter:card" content="summary">', '<meta name="twitter:card" content="summary_large_image">', 1)
    if 'name="twitter:image"' not in page:
        page = page.replace('</head>', f'  <meta name="twitter:image" content="{image}">\n</head>', 1)
    script = '<script id="stage31-root-jsonld" type="application/ld+json">' + _json_ld(root_structured_document(payload, events)) + '</script>'
    pattern = r'<script id="stage31-root-jsonld" type="application/ld\+json">.*?</script>'
    page = re.sub(pattern, script, page, count=1, flags=re.S) if re.search(pattern, page, flags=re.S) else page.replace('</head>', f'  {script}\n</head>', 1)
    return page

def render_sitemap(event_entries: list[tuple[str, str | None]], city_lastmod: dict[str, str | None]) -> str:
    static_entries = [
        (f"{SITE_BASE}/", city_lastmod.get("valparaiso")),
        (f"{SITE_BASE}/gijon/", city_lastmod.get("gijon")),
        (f"{SITE_BASE}/fuentes.html", None),
        (f"{SITE_BASE}/proponer-evento.html", None),
        (f"{SITE_BASE}/registrar-organizacion.html", None),
    ]
    rows = []
    for url, lastmod in [*static_entries, *sorted(set(event_entries))]:
        lastmod_xml = f"\n    <lastmod>{xml_escape(lastmod)}</lastmod>" if lastmod else ""
        rows.append(f"  <url>\n    <loc>{xml_escape(url)}</loc>{lastmod_xml}\n  </url>")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"


def generate(*, check: bool = False) -> dict[str, int]:
    for required in ("assets/event-page.css", "assets/event-page.js", "assets/accessibility.css", "assets/city-page.css"):
        if not (ROOT / required).exists():
            raise SystemExit(f"{required} is required")

    counts: dict[str, int] = {}
    event_entries: list[tuple[str, str | None]] = []
    city_lastmod: dict[str, str | None] = {}
    city_payloads: dict[str, dict[str, Any]] = {}
    city_events: dict[str, list[dict[str, Any]]] = {}
    paths: set[str] = set()

    for city_id, city in base.CITY_CONFIG.items():
        dataset_path: Path = city["dataset"]
        if not dataset_path.exists():
            raise SystemExit(f"Missing city dataset: {dataset_path}")
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        events = payload.get("events") or []
        if not isinstance(events, list):
            raise SystemExit(f"Invalid events array: {dataset_path}")
        stamp = base.generated_at(payload)
        lastmod = _lastmod(payload)
        changes = base.load_recent_changes(city.get("changes"), stamp)
        excluded = base.CITY_EXCLUDED_IDS.get(city_id, set())
        current = [event for event in events if isinstance(event, dict) and str(event.get("id") or "") not in excluded]
        counts[city_id] = len(current)
        city_lastmod[city_id] = lastmod
        city_payloads[city_id] = payload
        city_events[city_id] = current

        for event in current:
            slug = base.event_slug(event.get("id"))
            relative = f"evento/{city_id}/{slug}"
            if relative in paths:
                raise SystemExit(f"Duplicate generated event path: {relative}")
            paths.add(relative)
            event_url = base.page_url(city_id, event)
            page, ics = enhance_event_page(city_id, city, event, changes.get(str(event.get("id")), []), stamp)
            for required in (
                "<h1>",
                "application/ld+json",
                'rel="canonical"',
                'class="skip-link"',
                "assets/accessibility.css",
                'name="twitter:title"',
                'aria-label="Acciones del evento"',
            ):
                if required not in page:
                    raise SystemExit(f"Generated page missing {required}: {relative}")
            event_entries.append((event_url, lastmod))
            if not check:
                directory = ROOT / relative
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "index.html").write_text(page, encoding="utf-8")
                if ics:
                    (directory / "evento.ics").write_text(ics, encoding="utf-8", newline="")

    gijon_landing = render_city_landing("gijon", base.CITY_CONFIG["gijon"], city_payloads["gijon"], city_events["gijon"])
    for required in ("Agenda Cultural de Gijón / Xixón", "application/ld+json", 'rel="canonical"', 'class="skip-link"', "ItemList", "BreadcrumbList"):
        if required not in gijon_landing:
            raise SystemExit(f"Gijón landing page missing {required}")

    root_landing = render_root_landing(city_payloads["valparaiso"], city_events["valparaiso"])
    for required in ('lang="es-CL"', 'name="robots"', 'assets/accessibility.css', 'id="stage31-root-jsonld"', "CollectionPage", "ItemList", 'main id="contenido" tabindex="-1"'):
        if required not in root_landing:
            raise SystemExit(f"Valpo root landing page missing {required}")
    app_index = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    for required in ('data-stage31-accessibility', 'main id="contenido" tabindex="-1"'):
        if required not in app_index:
            raise SystemExit(f"PWA accessibility shell missing {required}")

    sitemap = render_sitemap(event_entries, city_lastmod)
    if f"{SITE_BASE}/gijon/" not in sitemap or f"{SITE_BASE}/app/" in sitemap:
        raise SystemExit("SEO sitemap canonical city contract failed")

    if not check:
        (ROOT / "index.html").write_text(root_landing, encoding="utf-8")
        gijon_dir = ROOT / "gijon"
        gijon_dir.mkdir(parents=True, exist_ok=True)
        (gijon_dir / "index.html").write_text(gijon_landing, encoding="utf-8")
        SITEMAP.write_text(sitemap, encoding="utf-8")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate stage 3.1 accessible, SEO-safe multi-city pages.")
    parser.add_argument("--check", action="store_true", help="Validate all generated pages in memory without writing files.")
    args = parser.parse_args()
    counts = generate(check=args.check)
    total = sum(counts.values())
    mode = "VALIDATED" if args.check else "GENERATED"
    breakdown = ", ".join(f"{city}={count}" for city, count in counts.items())
    print(f"STAGE31_SITE_{mode} total={total} {breakdown}")


if __name__ == "__main__":
    main()
