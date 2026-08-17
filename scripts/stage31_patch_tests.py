from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "tests" / "test_stage31.py"
text = path.read_text(encoding="utf-8")
old = '        self.assertEqual(payload["@type"], "Event")'
new = '        self.assertEqual(payload["@context"], "https://schema.org")\n        types = [item.get("@type") for item in payload["@graph"]]\n        self.assertIn("Event", types)\n        self.assertIn("BreadcrumbList", types)'
if new not in text:
    if old not in text:
        raise SystemExit("EVENT_TEST_ANCHOR_MISSING")
    text = text.replace(old, new, 1)

extra = '''\n\nclass Stage31CompletionTests(unittest.TestCase):
    def test_event_graph_contains_breadcrumbs(self):
        data = stage31.structured_page_document("valparaiso", sample_event(), "https://example.org/permalink/")
        self.assertEqual([item["@type"] for item in data["@graph"]], ["Event", "BreadcrumbList"])

    def test_root_landing_has_collection_and_accessibility_contract(self):
        page = stage31.render_root_landing({"generated_at": "2026-08-17T18:00:00-04:00"}, [sample_event()])
        self.assertIn('<html lang="es-CL">', page)
        self.assertIn('name="robots" content="index,follow,max-image-preview:large"', page)
        self.assertIn('assets/accessibility.css', page)
        self.assertIn('<main id="contenido" tabindex="-1">', page)
        match = re.search(r'<script id="stage31-root-jsonld" type="application/ld\\+json">(.*?)</script>', page, re.S)
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1).replace("<\\\\/", "</"))
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
'''
marker = '\n\nif __name__ == "__main__":\n    unittest.main()\n'
if "class Stage31CompletionTests" not in text:
    if marker not in text:
        raise SystemExit("UNITTEST_MARKER_MISSING")
    text = text.replace(marker, extra + marker, 1)
path.write_text(text, encoding="utf-8")
print("STAGE31_TEST_PATCH_OK")
