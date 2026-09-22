"""Static dispatch/writer boundaries for the distinct snapshot verifier."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def job(text, name):
    start = text.index("\n  " + name + ":\n")
    tail = text[start + 1:]
    next_job = re.search(r"\n  [a-z][a-z-]+:\n", tail)
    return tail[:next_job.start()] if next_job else tail


class SnapshotWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.publish = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
        self.watchdog = (ROOT / ".github/workflows/production-certification-watchdog.yml").read_text(encoding="utf-8")
        self.verify = job(self.publish, "verify-snapshot")
        self.smoke = job(self.publish, "snapshot-production-smoke")

    def test_explicit_mode_is_separate_and_partial_inputs_cannot_fall_back(self):
        self.assertIn("github.event_name == 'workflow_dispatch'", self.verify)
        for key in ("snapshot_public_sha", "original_run_id", "original_run_attempt"):
            self.assertIn(f"inputs.{key} != ''", self.verify)
            self.assertIn(f"inputs.{key} == ''", job(self.publish, "sync-cloudflare"))
        self.assertIn("needs: verify-snapshot", self.smoke)
        self.assertIn("group: publish-production", self.publish)
        self.assertNotIn("schedule:", self.publish)

    def test_no_candidate_writer_deployment_or_generation(self):
        for block in (self.verify, self.smoke):
            for forbidden in ("cloudflare-preview\n", "gh workflow run", "repository_dispatch",
                              "push origin HEAD:main", "--prepare", "cloudflare-build.sh", "finalize-public-agenda"):
                self.assertNotIn(forbidden, block)
        self.assertNotIn("contents: write", self.verify)
        self.assertEqual(self.smoke.count("push origin HEAD:"), 1)
        self.assertIn("push origin HEAD:state/production-certifications", self.smoke)
        self.assertIn("check-context --output", self.smoke)
        self.assertIn("snapshot_production_smoke.py", self.smoke)
        self.assertNotIn("--no-network", self.smoke)

    def test_attempts_artifacts_and_historical_snapshot_are_explicit(self):
        for block in (self.verify, self.smoke):
            self.assertIn("ref: ${{ github.sha }}", block)
            self.assertIn("ref: ${{ inputs.snapshot_public_sha }}", block)
            self.assertIn("path: .snapshot", block)
            self.assertIn("${{ github.run_id }}-${{ github.run_attempt }}", block)
            self.assertIn("retention-days: 30", block)

    def test_watchdog_does_not_impersonate_legacy_owner_or_write_state(self):
        for name in ("Inspect synchronized deployment outcome", "Download source production attestation",
                     "Require exact attestation lineage and durable chained certification"):
            block = self.watchdog.split("      - name: " + name, 1)[1].split("      - name:", 1)[0]
            self.assertIn("steps.routing.outputs.snapshot_verification != 'true'", block)
        self.assertIn("Verify exact snapshot certification", self.watchdog)
        self.assertNotIn("contents: write", self.watchdog)
        self.assertNotIn("git push", self.watchdog)
        callback = job(self.watchdog, "dispatch-snapshot-certification")
        self.assertNotIn("actions/checkout", callback)
        self.assertIn("permission-actions: write", callback)
        self.assertNotIn("permission-contents", callback)
        self.assertIn("CORE_CERTIFICATION_APP_ID", callback)
        self.assertEqual(callback.count("gh workflow run"), 1)
        self.assertIn("gh workflow run certify-publication-post-finalizer.yml", callback)
        self.assertIn('-f intent_id="$INTENT_ID"', callback)
        for key in ("web_verification_run_id", "web_verification_run_attempt", "web_watchdog_run_id", "web_watchdog_run_attempt"):
            self.assertIn("-f " + key + "=", callback)

    def test_rerun_rejection_is_unchanged(self):
        routing = (ROOT / "app/scripts/publication_execution_routing.py").read_text(encoding="utf-8")
        self.assertIn('binding.require(run_attempt == 1, "UNSUPPORTED_RERUN_REQUIRES_ORIGINAL_EXECUTION")', routing)

    def test_reference_clock_reaches_late_verifier_and_watchdog(self):
        for path, expected in (
            ("snapshot_production_smoke.py", "validate_reference_datasets(snapshot)"),
            ("production_release_chain.py", "validate_reference_datasets(Path.cwd())"),
            ("snapshot_verification_cli.py", "validate_reference_datasets(args.snapshot)"),
        ):
            self.assertIn(expected, (ROOT / "app/scripts" / path).read_text(encoding="utf-8"))


def run_contract():
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(SnapshotWorkflowTests))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    run_contract()
