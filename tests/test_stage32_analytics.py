from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Stage32AnalyticsTests(unittest.TestCase):
    def test_client_uses_first_party_worker_and_allowed_contract(self):
        text = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        self.assertIn("agenda-cultural-community.carlosggar.workers.dev/api/community/v1/analytics/events", text)
        for event in ("app_open", "event_open", "search", "filter_apply", "outbound_open", "share", "calendar_download", "install"):
            self.assertIn(f'"{event}"', text)
        for dimension in ("category", "eventId", "filter", "value", "target"):
            self.assertIn(dimension, text)

    def test_client_contains_no_visitor_identifier_or_raw_search_payload(self):
        text = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        forbidden = ("userId", "visitorId", "sessionId", "fingerprint", "document.cookie", "sendBeacon", "coords.latitude", "coords.longitude")
        for token in forbidden:
            self.assertNotIn(token, text)
        self.assertIn("rawSearchQueries: false", text)
        self.assertIn("coordinates: false", text)
        self.assertIn("rawUrls: false", text)
        self.assertNotIn("dimensions: { query", text)

    def test_search_tracking_never_serializes_search_text(self):
        text = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        self.assertIn('trackUsage("search")', text)
        self.assertNotIn('trackUsage("search", {', text)

    def test_web_pwa_event_pages_and_offline_cache_are_wired(self):
        pwa = (ROOT / "app" / "pwa.js").read_text(encoding="utf-8")
        web = (ROOT / "assets" / "web-event-enhancements.js").read_text(encoding="utf-8")
        event_page = (ROOT / "assets" / "event-page.js").read_text(encoding="utf-8")
        worker = (ROOT / "app" / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("usage-analytics.js?v=20260817-stage32", pwa)
        self.assertIn("usage-analytics.js?v=20260817-stage32", web)
        self.assertIn("usage-analytics.js?v=20260817-stage32", event_page)
        self.assertIn("usage-analytics.js?v=20260817-stage32", worker)

    def test_city_segmentation_is_explicit(self):
        text = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        self.assertIn('explicit === "gijon" || explicit === "valparaiso"', text)
        self.assertIn('return "gijon"', text)
        self.assertIn('return "valparaiso"', text)


if __name__ == "__main__":
    unittest.main()
