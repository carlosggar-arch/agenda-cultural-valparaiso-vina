from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_event_pages as base  # noqa: E402
import stage31_site_generator as stage31  # noqa: E402


def sample_event(**overrides):
    event = {
        "id": "agenda_test_001",
        "title": "Concierto de prueba",
        "event_type": "event",
        "primary_category": {"id": "musica", "label": "Música"},
        "categories": [{"id": "musica", "label": "Música"}],
        "schedule": {
            "start": "2026-08-22T20:00:00-04:00",
            "end": "2026-08-22T22:00:00-04:00",
        },
        "location": {
            "venue": "Teatro de prueba",
            "address": "Calle Cultura 123",
            "city": "Valparaíso",
            "online": False,
        },
        "price": {"is_free": None, "currency": "CLP", "min_amount": None, "display_text": "Por confirmar"},
        "links": {"official": "https://example.org/evento", "tickets": None, "registration": None, "source": "https://example.org/fuente"},
        "organizer": "Organización Cultural",
        "source_name": "Fuente de datos distinta",
        "source_url": "https://example.org/fuente",
        "description": "Una actividad cultural de prueba.",
        "public_status": {"cancelled": False, "sold_out": False},
        "image": {"url": "https://example.org/cartel.jpg", "alt": "Cartel del concierto"},
    }
    for key, value in overrides.items():
        event[key] = value
    return event


class StructuredDataTests(unittest.TestCase):
    def test_physical_dated_activity_is_event_without_unverified_offer(self):
        event = sample_event()
        data = stage31.structured_document("valparaiso", event, "https://example.org/permalink/")
        self.assertEqual(data["@type"], "Event")
        self.assertEqual(data["name"], event["title"])
        self.assertEqual(data["startDate"], event["schedule"]["start"])
        self.assertEqual(data["location"]["address"]["streetAddress"], "Calle Cultura 123")
        self.assertEqual(data["organizer"]["name"], "Organización Cultural")
        self.assertNotIn("offers", data)

    def test_data_source_is_never_promoted_to_organizer(self):
        event = sample_event(organizer=None)
        data = stage31.structured_document("valparaiso", event, "https://example.org/permalink/")
        self.assertNotIn("organizer", data)
        self.assertNotIn(event["source_name"], json.dumps(data, ensure_ascii=False))

    def test_verified_ticket_offer_has_complete_price_contract(self):
        event = sample_event(
            price={"is_free": False, "currency": "CLP", "min_amount": 8000, "display_text": "$8.000"},
            links={"official": "https://example.org/evento", "tickets": "https://example.org/entradas", "registration": None, "source": "https://example.org/fuente"},
        )
        data = stage31.structured_document("valparaiso", event, "https://example.org/permalink/")
        self.assertEqual(data["offers"]["url"], "https://example.org/entradas")
        self.assertEqual(data["offers"]["price"], 8000)
        self.assertEqual(data["offers"]["priceCurrency"], "CLP")

    def test_program_and_flexible_offer_are_not_mislabeled_as_event(self):
        program = sample_event(event_type="program")
        flexible = sample_event(event_type="flexible_offer", schedule={})
        self.assertEqual(stage31.structured_document("gijon", program, "https://example.org/programa/")["@type"], "CollectionPage")
        self.assertEqual(stage31.structured_document("gijon", flexible, "https://example.org/servicio/")["@type"], "Service")

    def test_online_only_activity_is_not_google_event_markup(self):
        event = sample_event(location={"venue": "Actividad en línea", "city": "Valparaíso", "online": True})
        self.assertNotEqual(stage31.structured_document("valparaiso", event, "https://example.org/online/")["@type"], "Event")


class ScheduleRenderingTests(unittest.TestCase):
    def test_same_day_timed_event_is_a_single_interval(self):
        self.assertEqual(
            base.schedule_text(sample_event()),
            "22 de agosto de 2026 · 20:00–22:00",
        )

    def test_flattened_multi_day_pairs_do_not_become_one_cross_day_interval(self):
        event = sample_event(schedule={
            "mode": "multi_day",
            "start": "2026-08-19T18:30:00-04:00",
            "end": "2026-08-22",
            "display_text": "2026-08-19 – 2026-08-22 · 18:30–20:00 · 10:00–14:00",
        })
        label = base.schedule_text(event)
        self.assertEqual(
            label,
            "19 de agosto de 2026 – 22 de agosto de 2026 · 18:30–20:00 · 10:00–14:00",
        )
        self.assertNotIn("18:30 – 22 de agosto", label)

    def test_all_day_sentinel_is_not_published(self):
        event = sample_event(schedule={
            "mode": "multi_day",
            "start": "2026-08-06",
            "end": "2026-10-04",
            "display_text": "6 ago – 4 oct · 00:00–23:59",
        })
        label = base.schedule_text(event)
        self.assertEqual(label, "6 de agosto de 2026 – 4 de octubre de 2026")
        self.assertNotIn("00:00", label)
        self.assertNotIn("23:59", label)

    def test_venue_opening_hours_are_separate_from_exhibition_dates(self):
        event = sample_event(schedule={
            "mode": "multi_day",
            "start": "2026-08-14",
            "end": "2026-10-04",
            "display_text": "2026-08-14 – 2026-10-04",
            "opening_hours": {
                "display_text": "Martes a domingo · 10:00–18:00",
            },
        })
        self.assertEqual(
            base.schedule_text(event),
            "14 de agosto de 2026 – 4 de octubre de 2026 · Martes a domingo · 10:00–18:00",
        )


class AccessibilitySeoRenderingTests(unittest.TestCase):
    def test_event_page_has_skip_link_focus_target_and_regional_metadata(self):
        event = sample_event()
        page, _ = stage31.enhance_event_page("valparaiso", base.CITY_CONFIG["valparaiso"], event, [], None)
        self.assertIn('<html lang="es-CL">', page)
        self.assertIn('class="skip-link" href="#contenido"', page)
        self.assertIn('<main id="contenido" class="event-page" tabindex="-1">', page)
        self.assertIn("assets/accessibility.css", page)
        self.assertIn('name="twitter:title"', page)
        self.assertIn('property="og:locale" content="es_CL"', page)
        self.assertIn('role="group" aria-label="Acciones del evento"', page)
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1).replace("<\\/", "</"))
        self.assertEqual(payload["@context"], "https://schema.org")
        types = [item.get("@type") for item in payload["@graph"]]
        self.assertIn("Event", types)
        self.assertIn("BreadcrumbList", types)

    def test_gijon_landing_is_static_indexable_collection(self):
        events = [sample_event(id="g1", title="Actividad uno"), sample_event(id="g2", title="Actividad dos")]
        payload = {"generated_at": "2026-08-17T19:00:00+02:00"}
        page = stage31.render_city_landing("gijon", base.CITY_CONFIG["gijon"], payload, events)
        self.assertIn('<link rel="canonical" href="https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina/gijon/">', page)
        self.assertIn('class="skip-link"', page)
        self.assertIn("ItemList", page)
        self.assertIn("../evento/gijon/g1/", page)
        self.assertIn("../app/?city=gijon", page)

    def test_sitemap_prefers_canonical_city_landing_over_app_shell(self):
        sitemap = stage31.render_sitemap(
            [("https://example.org/evento/", "2026-08-17")],
            {"valparaiso": "2026-08-17", "gijon": "2026-08-17"},
        )
        self.assertIn("/gijon/", sitemap)
        self.assertNotIn("/app/", sitemap)
        self.assertIn("<lastmod>2026-08-17</lastmod>", sitemap)

    def test_pwa_stage31_runtime_and_offline_assets_are_wired(self):
        pwa = (ROOT / "app" / "pwa.js").read_text(encoding="utf-8")
        worker = (ROOT / "app" / "service-worker.js").read_text(encoding="utf-8")
        runtime = (ROOT / "app" / "stage31-accessibility-seo.js").read_text(encoding="utf-8")
        css = (ROOT / "app" / "stage31-accessibility.css").read_text(encoding="utf-8")
        self.assertIn('import "./stage31-accessibility-seo.js";', pwa)
        self.assertIn('"./stage31-accessibility-seo.js"', worker)
        self.assertIn('"./stage31-accessibility.css"', worker)
        self.assertIn("aria-expanded", runtime)
        self.assertIn("node.inert = true", runtime)
        self.assertIn('event.key !== "Tab"', runtime)
        self.assertIn("focusableWithinChooser", runtime)
        self.assertIn(":focus-visible", css)
        self.assertIn("prefers-reduced-motion", css)


class Stage31CompletionTests(unittest.TestCase):
    def test_event_graph_contains_breadcrumbs(self):
        data = stage31.structured_page_document("valparaiso", sample_event(), "https://example.org/permalink/")
        self.assertEqual([item["@type"] for item in data["@graph"]], ["Event", "BreadcrumbList"])

    def test_root_landing_has_collection_and_accessibility_contract(self):
        page = stage31.render_root_landing({"generated_at": "2026-08-17T18:00:00-04:00"}, [sample_event()])
        self.assertIn('<html lang="es-CL">', page)
        self.assertIn('name="robots" content="index,follow,max-image-preview:large"', page)
        self.assertIn('assets/accessibility.css', page)
        self.assertIn('<main id="contenido" tabindex="-1">', page)
        match = re.search(r'<script id="stage31-root-jsonld" type="application/ld\+json">(.*?)</script>', page, re.S)
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1).replace("<\\/", "</"))
        types = [item.get("@type") for item in payload["@graph"]]
        self.assertIn("WebSite", types)
        self.assertIn("CollectionPage", types)

    def test_pwa_skip_link_has_static_styles_and_focusable_target(self):
        page = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-stage31-accessibility', page)
        self.assertIn('<main id="contenido" tabindex="-1">', page)

    def test_robots_points_to_canonical_sitemap(self):
        robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
        self.assertIn(f"Sitemap: {stage31.SITE_BASE}/sitemap.xml", robots)


if __name__ == "__main__":
    unittest.main()
