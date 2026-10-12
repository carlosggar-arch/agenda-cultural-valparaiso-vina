from __future__ import annotations

import json
import subprocess
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from test_production_probe_retry import load_smoke_module


class FixtureDriver:
    """Execute the actual probe JS against hidden/visible copies of one card."""

    def __init__(self, **options):
        self.options = options
        self.loading = []

    def execute_script(self, script, *args):
        harness = r"""
const fs = require('fs');
const {script, args, options} = JSON.parse(fs.readFileSync(0, 'utf8'));
const cards = [false, !options.hiddenOnly].map(visible => {
  const rect = {width: visible ? 271 : 0, height: visible ? 184 : 0};
  const image = {
    complete: true, naturalWidth: 1600, naturalHeight: 1067, loading: 'lazy',
    currentSrc: 'https://example.org/app/assets/event-images/valparaiso/' + (options.wrongFile ? 'wrong.webp' : 'official.webp'),
    dataset: {eventImage: 'relevant', eventImageId: args[0]},
    getBoundingClientRect: () => rect, getAttribute: () => 'official.webp',
  };
  return {
    image, getBoundingClientRect: () => rect,
    matches: () => Boolean(options.grouped),
    querySelector: selector => selector.startsWith('img') ? image : (options.placeholder ? {} : null),
  };
});
const document = {
  querySelector: () => cards[0], querySelectorAll: () => cards,
};
const getComputedStyle = () => ({visibility: 'visible'});
const result = new Function('document', 'getComputedStyle', 'return function(){' + script + '}')
  (document, getComputedStyle)(...args);
process.stdout.write(JSON.stringify({result, loading: cards.map(card => card.image.loading)}));
"""
        result = subprocess.run(
            ["node", "-e", harness], input=json.dumps({"script": script, "args": args, "options": self.options}),
            text=True, capture_output=True, check=True,
        )
        payload = json.loads(result.stdout)
        self.loading = payload["loading"]
        return payload["result"]


class ProductionImageSelectionTests(unittest.TestCase):
    def setUp(self):
        self.module = load_smoke_module()

    def test_hidden_featured_copy_does_not_shadow_visible_direct_or_grouped_card(self):
        for grouped in (False, True):
            driver = FixtureDriver(grouped=grouped)
            self.assertTrue(self.module.prepare_image_evidence(driver, "event"))
            self.assertEqual(driver.loading, ["lazy", "eager"])
            result = self.module.image_evidence(driver, "event", "official.webp")
            self.assertEqual(result["layoutWidth"], 271)
            self.assertEqual(result["eventImageId"], "event")
            self.assertEqual(result["presentation"], "grouped-exhibition" if grouped else "direct-card")
            diagnostic = self.module.image_diagnostics(driver, "event", "official.webp")
            self.assertEqual(diagnostic["layoutWidth"], result["layoutWidth"])

    def test_hidden_missing_or_wrong_official_image_never_passes(self):
        for options in ({"hiddenOnly": True}, {"wrongFile": True}, {"placeholder": True}):
            self.assertIsNone(self.module.image_evidence(FixtureDriver(**options), "event", "official.webp"))

    def test_web_surface_does_not_filter_out_selected_image_cases(self):
        today = datetime.now(ZoneInfo('America/Santiago')).date()
        def event(identity, image_hash, day):
            return {'id': identity, 'title': 'Official programme ' + identity,
                    'schedule': {'start': day.isoformat()},
                    'image': {'url': './assets/event-images/valparaiso/' + image_hash + '.webp',
                              'relevance': 'event_specific'}}
        # Exercise current capabilities without depending on expired live IDs.
        payload = {'timezone': 'America/Santiago', 'events': [
            event('expired-first', '0' * 24, today - timedelta(days=1)),
            event('current-a', 'a' * 24, today + timedelta(days=1)),
            event('current-b', 'b' * 24, today + timedelta(days=2)),
        ]}
        cases = self.module.resolve_official_image_cases(payload)
        selected = {event_id for event_id, _filename, _title in cases}
        self.assertEqual(selected, {'current-a', 'current-b'})
        self.assertEqual({filename for _id, filename, _title in cases},
                         {'a' * 24 + '.webp', 'b' * 24 + '.webp'})
        with self.assertRaisesRegex(ValueError, 'insufficient distinct current capabilities'):
            self.module.resolve_official_image_cases({**payload, 'events': payload['events'][:2]})

        surfaces = dict(self.module.official_image_surface_urls(
            "https://example.test/app/",
        ))
        query = parse_qs(urlparse(surfaces["web"]).query)
        self.assertEqual(query, {"periodo": ["todos"]})
        self.assertNotIn("q", query)


def run_contract():
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ProductionImageSelectionTests)
    )
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    run_contract()
