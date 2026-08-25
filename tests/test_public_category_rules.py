from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_event_pages as base  # noqa: E402
import stage31_site_generator as stage31  # noqa: E402
from public_category_rules import (  # noqa: E402
    canonical_public_category_id,
    is_public_category_in_group,
    resolve_public_category,
)

FIXTURES = json.loads((ROOT / "shared" / "public-category-fixtures.json").read_text(encoding="utf-8"))


class SharedPublicCategoryRulesTests(unittest.TestCase):
    def test_shared_multicity_fixtures(self):
        for fixture in FIXTURES["cases"]:
            with self.subTest(name=fixture["name"]):
                self.assertEqual(resolve_public_category(fixture["event"]), fixture["expected"])

    def test_shared_alias_helpers(self):
        self.assertEqual(
            canonical_public_category_id({"id": "formacion-taller", "label": "Formación / taller"}),
            "cursos-talleres-campus",
        )
        self.assertEqual(canonical_public_category_id({"id": "museos", "label": "Museos"}), "exposiciones")
        self.assertTrue(is_public_category_in_group({"id": "cursos-talleres"}, "training"))
        self.assertFalse(is_public_category_in_group({"id": "exposiciones"}, "training"))

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
                self.assertEqual(base.category_text(event), "Cursos, talleres y experiencias")

    def test_semantic_classification_is_city_and_source_neutral(self):
        semantic_payload = {
            "title": "Noche especial",
            "event_type": "event",
            "primary_category": {"id": "actividad-panorama", "label": "Actividad / panorama"},
            "description": "Bandas de punk y hardcore presentan canciones de sus nuevos discos.",
        }
        variants = (
            {**semantic_payload, "city": "Valparaíso", "source_id": "source_a", "source_name": "Fuente A"},
            {**semantic_payload, "city": "Gijón", "source_id": "source_b", "source_name": "Fuente B"},
        )
        resolved = [resolve_public_category(event) for event in variants]
        self.assertEqual(resolved[0], {"id": "musica", "label": "Música"})
        self.assertEqual(resolved[1], resolved[0])

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
        self.assertEqual(page.count('class="city-eyebrow">Cursos, talleres y experiencias</p>'), 2)
        self.assertNotIn('class="city-eyebrow">Formación / taller</p>', page)


if __name__ == "__main__":
    unittest.main()
