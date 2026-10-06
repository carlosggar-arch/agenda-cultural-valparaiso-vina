from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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
        payload = json.loads(Path("agenda_web.json").read_text(encoding="utf-8"))
        cases = self.module.resolve_official_image_cases(payload)
        selected = {event_id for event_id, _filename, _title in cases}
        self.assertEqual(selected, {
            "agenda_03659e6e66f6d530eb04721c",
            "agenda_040947b00f9418953022105b",
        })

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
