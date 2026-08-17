from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Stage32AnalyticsTests(unittest.TestCase):
    def test_client_is_first_party_aggregate_and_has_no_identity_or_raw_search_payload(self):
        js = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        self.assertIn("/community/v1/analytics/events", js)
        self.assertIn('const PUBLIC_ORIGIN = "https://carlosggar-arch.github.io"', js)
        self.assertIn("location.origin !== PUBLIC_ORIGIN", js)
        self.assertIn('credentials: "omit"', js)
        self.assertIn('referrerPolicy: "no-referrer"', js)
        self.assertIn("globalPrivacyControl", js)
        self.assertIn("navigator.doNotTrack", js)
        self.assertIn('dimension: "search_length"', js)
        self.assertIn('"10plus"', js)
        self.assertNotRegex(js, re.compile(r"cookie|fingerprint|session[_-]?id|user[_-]?id", re.I))
        self.assertNotIn("input.value.trim() }", js)

    def test_city_detection_accepts_future_safe_registry_ids(self):
        js = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        self.assertIn("const safeCity =", js)
        self.assertIn("^[a-z0-9][a-z0-9-]{0,63}$", js)
        self.assertIn("if (dataCity) return dataCity", js)
        self.assertNotIn('dataCity === "gijon" || dataCity === "valparaiso"', js)

    def test_all_primary_surfaces_load_the_same_analytics_client(self):
        root = (ROOT / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
        generator = (ROOT / "scripts" / "generate_event_pages.py").read_text(encoding="utf-8")
        stage31 = (ROOT / "scripts" / "stage31_site_generator.py").read_text(encoding="utf-8")
        self.assertIn("assets/usage-analytics.js", root)
        self.assertIn("../assets/usage-analytics.js", app)
        self.assertIn("../../../assets/usage-analytics.js", generator)
        self.assertIn("../assets/usage-analytics.js", stage31)

    def test_pwa_caches_analytics_runtime_but_never_caches_analytics_requests(self):
        worker = (ROOT / "app" / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn('"../assets/usage-analytics.js"', worker)
        self.assertIn('request.method !== "GET"', worker)

    def test_privacy_page_discloses_aggregate_measurement(self):
        privacy = (ROOT / "privacidad.html").read_text(encoding="utf-8")
        for text in ["analítica", "agreg", "cookies", "texto de búsqueda", "Global Privacy Control"]:
            self.assertIn(text.casefold(), privacy.casefold())


if __name__ == "__main__":
    unittest.main()
