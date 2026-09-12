from __future__ import annotations

import unittest
import hashlib
from unittest.mock import patch

import deployment_readiness as readiness


def ready_rows():
    return {name: {"origin": name, "ready": True, "reason": "byte-identical"}
            for name in readiness.ORIGINS}


def mismatched_rows():
    rows = ready_rows()
    rows["cloudflare"] = {
        "origin": "cloudflare", "ready": False, "reason": "content-mismatch",
        "mismatches": ["../agenda_web.json"],
    }
    return rows


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class DeploymentReadinessTest(unittest.TestCase):
    def test_content_mismatch_reports_both_digests_without_accepting_it(self):
        expected = hashlib.sha256(b"expected diagnostic bytes").hexdigest()
        observed = hashlib.sha256(b"different diagnostic bytes").hexdigest()
        with patch.object(readiness, "fetch_text", return_value="const RELEASE = 251;"), \
                patch.object(readiness, "CRITICAL_ASSETS", (("agenda_web.json", "../agenda_web.json"),)), \
                patch.object(readiness, "local_hash", return_value=expected), \
                patch.object(readiness, "_remote_hash", return_value=("../agenda_web.json", observed)):
            row = readiness.probe_origin("cloudflare", "https://diagnostic.invalid/app/", 251)
        self.assertFalse(row["ready"])
        self.assertEqual(row["hashes"]["../agenda_web.json"], {
            "expected_sha256": expected, "observed_sha256": observed,
        })

    def test_confirmation_mismatch_stays_in_original_wait_budget(self):
        clock = Clock()
        with patch.object(readiness, "probe_all", side_effect=[
            ready_rows(), mismatched_rows(), ready_rows(), ready_rows(),
        ]) as probe, patch.object(readiness, "verify_shell_once") as shell, \
                patch.object(readiness.time, "monotonic", clock.monotonic), \
                patch.object(readiness.time, "sleep", clock.sleep):
            rows, elapsed = readiness.wait_until_ready(251, 90, 2)
        self.assertEqual(rows, ready_rows())
        self.assertEqual(elapsed, 2)
        self.assertEqual(probe.call_count, 4)
        self.assertEqual(shell.call_count, len(readiness.ORIGINS))

    def test_persistently_mismatched_confirmation_times_out(self):
        clock = Clock()
        count = 0

        def probe(_release):
            nonlocal count
            count += 1
            return ready_rows() if count % 2 else mismatched_rows()

        with patch.object(readiness, "probe_all", probe), \
                patch.object(readiness, "verify_shell_once") as shell, \
                patch.object(readiness.time, "monotonic", clock.monotonic), \
                patch.object(readiness.time, "sleep", clock.sleep):
            with self.assertRaisesRegex(SystemExit, "DEPLOYMENT_READINESS_TIMEOUT.*cloudflare"):
                readiness.wait_until_ready(251, 90, 2)
        self.assertEqual(clock.now, 90)
        shell.assert_not_called()

    def test_one_shot_assertion_never_retries(self):
        with patch.object(readiness, "probe_all", return_value=mismatched_rows()) as probe, \
                patch.object(readiness.time, "sleep") as sleep, \
                patch.object(readiness, "verify_shell_once") as shell:
            with self.assertRaisesRegex(SystemExit, "DEPLOYMENT_NOT_READY.*agenda_web.json"):
                readiness.assert_all_ready(251)
        probe.assert_called_once_with(251)
        sleep.assert_not_called()
        shell.assert_not_called()

    def test_shell_failure_is_not_downgraded_to_propagation(self):
        with patch.object(readiness, "probe_all", return_value=ready_rows()), \
                patch.object(readiness, "verify_shell_once", side_effect=SystemExit("DEPLOYMENT_SHELL_STALE")), \
                patch.object(readiness.time, "sleep") as sleep:
            with self.assertRaisesRegex(SystemExit, "DEPLOYMENT_SHELL_STALE"):
                readiness.wait_until_ready(251, 90, 2)
        sleep.assert_not_called()

    def test_missing_origin_cannot_satisfy_parity(self):
        rows = ready_rows()
        del rows["cloudflare"]
        with patch.object(readiness, "probe_all", return_value=rows), \
                patch.object(readiness, "verify_shell_once") as shell:
            with self.assertRaisesRegex(SystemExit, "DEPLOYMENT_NOT_READY.*cloudflare"):
                readiness.assert_all_ready(251)
        shell.assert_not_called()


def run_contract():
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DeploymentReadinessTest)
    )
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    run_contract()
