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
        self.assertLess(raw.index("Initialize failure-safe diagnostic evidence"), raw.index("id: app-token"))
        initialization = raw.split("Initialize failure-safe diagnostic evidence", 1)[1].split(
            "Mint exact Core diagnostic installation token", 1
        )[0]
        self.assertNotIn("secrets.", initialization)
        self.assertNotIn("GH_TOKEN", initialization)
        self.assertIn("diagnostic/web-execution.json", raw)
        self.assertIn("authentication_pending > diagnostic/result.txt", raw)
        self.assertIn("permission-actions: write", raw)
        self.assertEqual(raw.count("permission-contents: read"), 1)
        self.assertIn("test \"$APP_SLUG\" = agenda-core-certification", raw)
        self.assertIn("installation/repositories", raw)
        self.assertEqual(raw.count("gh workflow run"), 1)
        self.assertIn("private-attestation-diagnostic.yml", raw)
        self.assertIn('-f request_nonce="$nonce"', raw)
        self.assertIn("private-attestation-diagnostic-${run_id}-1", raw)
        self.assertIn('run_dir="diagnostic/candidates/$run_id"', raw)
        self.assertIn('candidate_dir="$(mktemp -d "$run_dir/artifact.XXXXXX")"', raw)
        self.assertIn('mv "$candidate_dir" "$run_dir/artifact"', raw)
        self.assertIn('touch "$run_dir/processed"', raw)
        self.assertIn("diagnostic/matched-core-run", raw)
        self.assertNotIn("rm -rf diagnostic/candidate", raw)
        self.assertGreaterEqual(raw.count(".request_nonce == $nonce and .core_sha == $core_sha"), 2)
        self.assertGreaterEqual(raw.count(".signer == {run_id:$run_id, run_attempt:1}"), 2)
        self.assertGreaterEqual(raw.count(".databaseId == $run_id and .attempt == 1"), 2)
        self.assertIn("retention-days: 7", raw)
        for forbidden in (
            "publish.yml", "finalize", "publisher", "cloudflare-preview", "push origin",
            "contents: write", "repository_dispatch", "apify", "pytesseract",
        ):
            self.assertNotIn(forbidden, raw.lower())

    def test_production_callback_remains_actions_only(self):
        raw = (ROOT / ".github/workflows/production-certification-watchdog.yml").read_text(encoding="utf-8")
        callback = raw.split("id: callback-token", 1)[1].split("- name: Request official Core certification", 1)[0]
        self.assertIn("permission-actions: write", callback)
        self.assertNotIn("permission-contents:", callback)
        self.assertNotIn("contents: write", callback)


if __name__ == "__main__":
    unittest.main()
