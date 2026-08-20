from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Stage32AnalyticsTests(unittest.TestCase):
    def test_client_matches_current_backend_contract(self):
        text = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        self.assertIn("agenda-cultural-community.carlosggar.workers.dev/community/v1/analytics/events", text)
        for event in (
            "landing_view", "app_open", "event_open", "city_select", "filter_use", "search_use",
            "outbound_open", "calendar_download", "share", "app_install",
        ):
            self.assertIn(f'"{event}"', text)
        self.assertIn('JSON.stringify({ events: [item] })', text)
        for field in ("dimension", "value", "event_id"):
            self.assertIn(field, text)

    def test_client_contains_no_visitor_identifier_or_raw_search_payload(self):
        text = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        forbidden = (
            "userId", "visitorId", "sessionId", "fingerprint", "document.cookie", "sendBeacon",
            "coords.latitude", "coords.longitude", "referrer", "userAgent",
        )
        for token in forbidden:
            self.assertNotIn(token, text)
        self.assertIn("rawSearchQueries: false", text)
        self.assertIn("coordinates: false", text)
        self.assertIn("rawUrls: false", text)

    def test_search_sends_only_length_bucket(self):
        text = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        self.assertIn('trackUsage("search_use", { dimension: "search_length", value: bucket })', text)
        self.assertIn('return "2-4"', text)
        self.assertIn('return "5-9"', text)
        self.assertIn('return "10plus"', text)
        self.assertNotIn("input.value,", text)

    def test_global_privacy_control_and_do_not_track_are_honored(self):
        text = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        self.assertIn("navigator.globalPrivacyControl === true", text)
        self.assertIn('navigator.doNotTrack === "1"', text)
        self.assertIn('window.doNotTrack === "1"', text)
        self.assertIn("if (privacySignalEnabled()) return false", text)

    def test_web_pwa_event_pages_and_offline_cache_are_wired(self):
        pwa = (ROOT / "app" / "pwa.js").read_text(encoding="utf-8")
        web = (ROOT / "assets" / "web-event-enhancements.js").read_text(encoding="utf-8")
        event_page = (ROOT / "assets" / "event-page.js").read_text(encoding="utf-8")
        worker = (ROOT / "app" / "service-worker.js").read_text(encoding="utf-8")
        shell_manifest = (ROOT / "app" / "service-worker-assets.generated.js").read_text(encoding="utf-8")
        self.assertIn("usage-analytics.js?v=20260817-stage32", pwa)
        self.assertIn("usage-analytics.js?v=20260817-stage32", web)
        self.assertIn("usage-analytics.js?v=20260817-stage32", event_page)
        self.assertIn("service-worker-assets.generated.js", worker)
        self.assertIn('"../assets/usage-analytics.js"', shell_manifest)

    def test_city_model_is_extensible_and_known_cities_are_detected(self):
        text = (ROOT / "assets" / "usage-analytics.js").read_text(encoding="utf-8")
        self.assertIn('/^[a-z0-9][a-z0-9-]{0,63}$/.test(explicit)', text)
        self.assertIn('return "gijon"', text)
        self.assertIn('return "valparaiso"', text)


if __name__ == "__main__":
    unittest.main()
