"""Static boundary for the one-shot Actions-only App authentication probe."""
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]


class AppAuthenticationDiagnosticTests(unittest.TestCase):
    def test_diagnostic_is_manual_actions_only_and_not_a_writer(self):
        path = ROOT / ".github/workflows/core-certification-app-auth-diagnostic.yml"
        raw = path.read_text(encoding="utf-8")
        workflow = yaml.load(raw, Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["jobs"]), {"diagnostic"})
        self.assertIn("permission-actions: write", raw)
        self.assertIn("test \"$APP_SLUG\" = agenda-core-certification", raw)
        self.assertIn("installation/repositories", raw)
        self.assertEqual(raw.count("gh workflow run"), 1)
        self.assertIn("private-attestation-diagnostic.yml", raw)
        self.assertIn('-f request_nonce="$nonce"', raw)
        self.assertIn("private-attestation-diagnostic-${run_id}-1", raw)
        self.assertIn("retention-days: 7", raw)
        for forbidden in (
            "publish.yml", "finalize", "publisher", "cloudflare-preview", "push origin",
            "contents: write", "repository_dispatch", "apify", "pytesseract",
        ):
            self.assertNotIn(forbidden, raw.lower())


if __name__ == "__main__":
    unittest.main()
