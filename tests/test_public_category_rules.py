from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_event_pages as base  # noqa: E402
import stage31_site_generator as stage31  # noqa: E402
from public_category_rules import resolve_public_category  # noqa: E402


class SharedPublicCategoryRulesTests(unittest.TestCase):
    def test_gijon_summer_registration_program_uses_shared_training_category(self):
        event = {
            "id": "agenda_gijon_summer",
            "title": "Gijón Verano: inscripciones",
            "event_type": "program",
            "primary_category": {"id": "cultura", "label": "Cultura"},
            "categories": [{"id": "cultura", "label": "Cultura"}],
        }
        self.assertEqual(
            resolve_public_category(event),
            {"id": "cursos-talleres-campus", "label": "Cursos, talleres y campus"},
        )

    def test_old_training_aliases_are_merged_for_all_cities(self):
        for category_id, label in (
            ("formacion-taller", "Formación / taller"),
            ("cursos-talleres", "Cursos y talleres"),
            ("formacion", "Formación"),
        ):
            with self.subTest(category_id=category_id):
                event = {
                    "title": "Actividad formativa",
                    "event_type": "event",
                    "primary_category": {"id": category_id, "label": label},
                    "categories": [{"id": category_id, "label": label}],
                }
                self.assertEqual(base.category_text(event), "Cursos, talleres y campus")

    def test_laboral_summer_campus_is_training_even_as_dated_event(self):
        event = {
            "title": "Campus de Verano de la Laboral 2026",
            "event_type": "event",
            "primary_category": {"id": "formacion-taller", "label": "Formación / taller"},
            "categories": [{"id": "formacion-taller", "label": "Formación / taller"}],
        }
        self.assertEqual(base.category_text(event), "Cursos, talleres y campus")

    def test_specific_nature_activity_keeps_its_specific_category(self):
        event = {
            "title": "Ruta de senderismo por la costa",
            "event_type": "event",
            "primary_category": {"id": "naturaleza-deportes", "label": "Naturaleza y deportes"},
            "categories": [{"id": "naturaleza-deportes", "label": "Naturaleza y deportes"}],
        }
        self.assertEqual(base.category_text(event), "Naturaleza y deportes")

    def test_static_gijon_landing_uses_canonical_shared_labels(self):
        events = [
            {
                "id": "agenda_gijon_summer",
                "title": "Gijón Verano: inscripciones",
                "event_type": "program",
                "primary_category": {"id": "cultura", "label": "Cultura"},
                "categories": [{"id": "cultura", "label": "Cultura"}],
                "schedule": {"start": "2026-08-21", "end": "2026-08-31", "display_text": "2026-08-21 – 2026-08-31"},
                "location": {"venue": "Gijón/Xixón", "city": "Gijón", "online": False},
                "image": {"url": None},
            },
            {
                "id": "gijon_laboral_campus",
                "title": "Campus de Verano de la Laboral 2026",
                "event_type": "event",
                "primary_category": {"id": "formacion-taller", "label": "Formación / taller"},
                "categories": [{"id": "formacion-taller", "label": "Formación / taller"}],
                "schedule": {"start": "2026-08-22", "end": "2026-08-22", "display_text": "2026-08-22"},
                "location": {"venue": "Laboral Ciudad de la Cultura", "city": "Gijón", "online": False},
                "image": {"url": None},
            },
        ]
        page = stage31.render_city_landing(
            "gijon",
            base.CITY_CONFIG["gijon"],
            {"generated_at": "2026-08-21T02:00:00+02:00"},
            events,
        )
        self.assertEqual(page.count('class="city-eyebrow">Cursos, talleres y campus</p>'), 2)
        self.assertNotIn('class="city-eyebrow">Formación / taller</p>', page)


if __name__ == "__main__":
    unittest.main()
