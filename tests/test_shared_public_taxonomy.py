from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT / "shared" / "public-category-taxonomy.json"
DATASETS = (
    ROOT / "agenda_web.json",
    ROOT / "app" / "data" / "gijon" / "agenda_web.json",
)


class SharedPublicTaxonomyArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = TAXONOMY_PATH.read_text(encoding="utf-8")
        cls.taxonomy = json.loads(cls.raw)

    def test_canonical_structure_is_self_consistent(self):
        categories = self.taxonomy["categories"]
        self.assertTrue(categories)
        self.assertIn(self.taxonomy["fallback_category"], categories)

        for category_id, config in categories.items():
            self.assertRegex(category_id, r"^[a-z0-9-]+$")
            self.assertTrue(str(config.get("label") or "").strip())
            self.assertTrue(str(config.get("symbol") or "").strip())

        for alias, target in self.taxonomy["aliases"].items():
            self.assertNotIn(alias, categories, f"alias must not duplicate canonical id: {alias}")
            self.assertIn(target, categories, f"alias target does not exist: {alias} -> {target}")

        for target in self.taxonomy["label_aliases"].values():
            self.assertIn(target, categories)

        for group, members in self.taxonomy["groups"].items():
            self.assertTrue(members, f"empty shared category group: {group}")
            for category_id in members:
                self.assertIn(category_id, categories)

        for rule_set in ("explicit_title", "culture_evidence"):
            for rule in self.taxonomy["rules"][rule_set]:
                self.assertIn(rule["category"], categories)
                re.compile(rule["pattern"])

        re.compile(self.taxonomy["rules"]["summer_program_title_pattern"])
        re.compile(self.taxonomy["rules"]["summer_registration_title_pattern"])

    def test_taxonomy_has_no_city_specific_branching(self):
        folded = self.raw.casefold()
        forbidden = ("valparaiso", "valparaíso", "viña del mar", "gijon", "gijón", "xixon", "xixón")
        for token in forbidden:
            self.assertNotIn(token, folded, f"city-specific token leaked into shared taxonomy: {token}")

    def test_current_city_source_categories_are_registered(self):
        registered = set(self.taxonomy["registered_source_ids"])
        canonical = set(self.taxonomy["categories"])
        missing: dict[str, set[str]] = {}
        for dataset_path in DATASETS:
            payload = json.loads(dataset_path.read_text(encoding="utf-8"))
            for event in payload.get("events") or []:
                source = event.get("primary_category") or {}
                category_id = str(source.get("id") or "").strip().casefold()
                if category_id and category_id not in registered and category_id not in canonical:
                    missing.setdefault(dataset_path.name, set()).add(category_id)
        if missing:
            detail = "; ".join(
                f"{name}: {', '.join(sorted(values))}" for name, values in sorted(missing.items())
            )
            self.fail(f"UNREGISTERED_PUBLIC_SOURCE_CATEGORIES: {detail}")

    def test_registry_is_unique_and_sorted(self):
        registered = self.taxonomy["registered_source_ids"]
        self.assertEqual(len(registered), len(set(registered)))
        self.assertEqual(registered, sorted(registered))

    def test_runtime_owners_do_not_redeclare_shared_category_sets(self):
        forbidden_by_file = {
            ROOT / "app" / "public-category-rules.mjs": ("const CATEGORY =", "TRAINING_CATEGORY_IDS"),
            ROOT / "scripts" / "public_category_rules.py": ("TRAINING_CATEGORY_IDS", "CATEGORY = {"),
            ROOT / "app" / "formation-cycle-classifier.js": ("TRAINING_CATEGORY_IDS",),
            ROOT / "app" / "exhibition-group-core.mjs": ("EXHIBITION_IDS",),
            ROOT / "app" / "card-experience.js": ("CATEGORY_SYMBOLS",),
        }
        for path, forbidden_tokens in forbidden_by_file.items():
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, text, f"duplicated shared taxonomy in {path.relative_to(ROOT)}: {token}")

    def test_card_presentation_consumes_shared_taxonomy(self):
        text = (ROOT / "app" / "card-experience.js").read_text(encoding="utf-8")
        self.assertIn("publicCategorySymbol", text)
        self.assertIn("publicEventTypeLabel", text)
        self.assertIn("canonicalPublicCategoryId", text)


if __name__ == "__main__":
    unittest.main()
