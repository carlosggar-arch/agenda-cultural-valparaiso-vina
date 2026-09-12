"""Deterministic routing tests; crypto originals remain owned by the consumer."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import publication_execution_binding as binding
import publication_execution_routing as routing
from test_publication_execution_github import example_binding, execution_fixture, FixtureAPI
from publication_execution_github import GithubReader

ROOT = Path(__file__).resolve().parents[2]


class PublicationExecutionRoutingTests(unittest.TestCase):
    def setUp(self):
        self.expected = example_binding()
        self.index = binding.build_index(binding=self.expected, run_id=20, run_attempt=1,
                                         workflow_head_sha="f" * 40)
        self.reader = Mock()
        self.reader.prefix = "repos/" + binding.WEB_REPOSITORY
        self.reader.code_hashes.return_value = {path: "9" * 40 for path in binding.CODE_PATHS}
        self.reader.api.return_value = {"object": {"sha": self.expected["public_sha"]}}
        self.reader.observations.return_value = {"verified": [], "pending": [], "suspect": [], "unstarted": []}
        self.verified = patch.object(routing, "verified_bytes", return_value=(self.expected, "2026-09-12T12:00:00Z"))
        self.retained = patch.object(routing, "existing_certification", return_value=None)
        self.verified.start()
        self.mock_retained = self.retained.start()
        self.addCleanup(self.verified.stop)
        self.addCleanup(self.retained.stop)

    def prepare(self, **overrides):
        return routing.prepare_core(**({"root": ROOT, "lineage_dir": Path("/local-test-only"),
                                        "run_id": 21, "run_attempt": 1, "workflow_head_sha": "f" * 40,
                                        "reader": self.reader, "state_root": Path("/local-test-state")} | overrides))

    def test_preliminary_push_is_not_no_release_or_authority(self):
        value = routing.ordinary_route({"event": "push", "release": True, "no_release": False,
                                        "reason": "release-diff-requires-full-lineage"})
        self.assertEqual(value["action"], "awaiting_authenticated_lineage")
        self.assertEqual(value["publication_state"], "NOT_CERTIFIED")
        self.assertEqual(value["authority"], "unverified")
        self.assertFalse(value["deployed"])
        self.assertNotIn("core_execution", value)

    def test_no_release_and_pr_release_remain_distinct(self):
        self.assertEqual(routing.ordinary_route({"release": False, "no_release": True}), {"action": "no_release"})
        self.assertEqual(routing.ordinary_route({"event": "push", "release": True, "no_release": False,
                                                "reason": "trusted-pr-impact"}), {"action": "publish"})

    def test_missing_or_contradictory_classification_blocks(self):
        for value in ({}, {"release": True}, {"release": False, "no_release": False},
                      {"release": "false", "no_release": True}):
            with self.subTest(value=value), self.assertRaises(binding.ExecutionBindingError):
                routing.ordinary_route(value)

    def test_first_authenticated_delivery_claims_root_only_on_current_main(self):
        value = self.prepare()
        self.assertEqual(value["action"], "publish")
        self.assertEqual(value["core_execution"]["canonical"], {"run_id": 21, "run_attempt": 1})
        self.reader.api.assert_called_once_with(self.reader.prefix + "/git/ref/heads/main")

    def test_rerun_cannot_replace_the_original_owner(self):
        with self.assertRaisesRegex(binding.ExecutionBindingError, "UNSUPPORTED_RERUN_REQUIRES_ORIGINAL_EXECUTION"):
            self.prepare(run_attempt=2)
        self.reader.observations.assert_not_called()
        self.reader.api.assert_not_called()

    def test_unstarted_queued_duplicate_does_not_block_then_delegates(self):
        self.reader.observations.return_value["unstarted"] = [{"run": {"id": 22}, "reason": "delivery-not-started"}]
        first = self.prepare()
        self.reader.observations.return_value = {"verified": [{"index": first["core_execution"]}],
                                                "pending": [], "suspect": [], "unstarted": []}
        second = self.prepare(run_id=22)
        self.assertEqual(second["action"], "delegated")
        self.assertEqual(second["core_execution"]["canonical"], first["core_execution"]["canonical"])

    def test_exact_duplicate_and_failed_owner_never_redeploy(self):
        for conclusion in ("success", "failure"):
            self.reader.observations.return_value["verified"] = [{"index": self.index, "run": {"conclusion": conclusion}}]
            value = self.prepare()
            self.assertEqual(value["action"], "delegated")
            self.assertEqual(value["core_execution"]["canonical"], self.index["canonical"])
        self.reader.api.assert_not_called()

    def test_existing_certification_requires_same_verified_root(self):
        self.mock_retained.return_value = {"index": self.index, "path": "certifications/local.json", "archive_sha256": "1" * 64}
        with self.assertRaisesRegex(binding.ExecutionBindingError, "RETAINED_EXECUTION_PROOF_MISSING"):
            self.prepare()
        self.reader.observations.return_value["verified"] = [{"index": self.index}]
        value = self.prepare()
        self.assertEqual(value["action"], "delegated")
        self.assertIsNotNone(value["retained_certification"])

    def test_prior_active_or_failed_unproven_delivery_blocks_new_root(self):
        for name in ("pending", "suspect"):
            self.reader.observations.return_value[name] = [{"run": {"id": 20}}]
            with self.subTest(name=name), self.assertRaisesRegex(binding.ExecutionBindingError, "PRIOR_EXECUTION_UNPROVEN"):
                self.prepare()
            self.reader.observations.return_value[name] = []

    def test_stale_uncertified_callback_cannot_roll_back_mirror(self):
        self.reader.api.return_value = {"object": {"sha": "0" * 40}}
        with self.assertRaisesRegex(binding.ExecutionBindingError, "STALE_UNCERTIFIED_CANDIDATE"):
            self.prepare()

    def test_late_workflow_with_changed_verifier_code_blocks(self):
        self.reader.code_hashes.side_effect = [{path: "8" * 40 for path in binding.CODE_PATHS},
                                             {path: "8" * 40 for path in binding.CODE_PATHS},
                                             {path: "9" * 40 for path in binding.CODE_PATHS}]
        with self.assertRaisesRegex(binding.ExecutionBindingError, "UNAUTHORISED_WORKFLOW_CODE"):
            self.prepare()
        self.reader.observations.assert_not_called()

    def test_checked_out_candidate_code_must_match_parent_before_any_claim(self):
        self.reader.code_hashes.side_effect = [{path: "8" * 40 for path in binding.CODE_PATHS},
                                             {path: "9" * 40 for path in binding.CODE_PATHS}]
        with self.assertRaisesRegex(binding.ExecutionBindingError, "UNAUTHORISED_CANDIDATE_CODE"):
            self.prepare()
        self.reader.observations.assert_not_called()

    def test_two_roots_or_crossed_identity_block(self):
        second = binding.build_index(binding=self.expected, run_id=25, run_attempt=1, workflow_head_sha="f" * 40)
        self.reader.observations.return_value["verified"] = [{"index": self.index}, {"index": second}]
        with self.assertRaisesRegex(binding.ExecutionBindingError, "CONTRADICTORY_ROOTS"):
            self.prepare()

    def test_restore_index_requires_exact_workflow_head(self):
        with tempfile.TemporaryDirectory(prefix="routing-index-") as directory:
            env = {"GITHUB_RUN_ID": "20", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "0" * 40}
            argv = ["routing", "--restore-index", binding.encode_notice(self.index), "--output-dir", directory]
            with patch.dict(os.environ, env), patch("sys.argv", argv):
                with self.assertRaisesRegex(binding.ExecutionBindingError, "RESTORED_EXECUTION_INVALID"):
                    routing.main()
            self.assertFalse(list(Path(directory).iterdir()))
            env["GITHUB_SHA"] = "f" * 40
            with patch.dict(os.environ, env), patch("sys.argv", argv):
                routing.main()
            self.assertEqual(json.loads((Path(directory) / "core-execution.json").read_text()), self.index)

    def _watchdog_fixture(self, index):
        fixture = execution_fixture(index)
        sync = fixture["job"]
        sync["steps"].extend({"name": name, "status": "completed", "conclusion": "skipped", "number": n}
                             for n, name in enumerate(routing.release_routing.DEPLOYMENT_STEPS, 10))
        sync["steps"].append({"name": "Preserve verified deployment routing evidence", "status": "completed", "conclusion": "success", "number": 3})
        api = FixtureAPI(fixture)
        prefix = "repos/" + binding.WEB_REPOSITORY
        endpoint = f"{prefix}/actions/runs/{fixture['run']['id']}/attempts/1/jobs?per_page=100&page=1"
        jobs = [sync]
        for name in ("production-smoke", "refresh-open-release-prs"):
            jobs.append({"name": name, "run_id": fixture["run"]["id"], "run_attempt": 1,
                         "head_sha": fixture["run"]["head_sha"], "conclusion": "skipped", "status": "completed"})
        api.overrides[endpoint] = {"total_count": 3, "jobs": jobs}
        reader = GithubReader(api=api, code_resolver=lambda sha, paths: {path: "9" * 40 for path in paths})
        return fixture, reader

    def test_canonical_watchdog_uses_signed_public_not_dispatch_workflow_head(self):
        _, reader = self._watchdog_fixture(self.index)
        with self.assertRaisesRegex(binding.ExecutionBindingError, "CANONICAL_CERTIFICATION_MISSING"):
            routing.watchdog(root=ROOT, state_root=Path("/fixture"), run_id=20, reader=reader)
        self.mock_retained.return_value = {"index": self.index, "attestation_sha256": "1" * 64}
        result = routing.watchdog(root=ROOT, state_root=Path("/fixture"), run_id=20, reader=reader)
        self.assertEqual(result, {"no_release": False, "delegated": False, "effective_head": self.expected["public_sha"],
                                  "execution_index": binding.encode_notice(self.index), "attestation_sha256": "1" * 64})

    def test_preliminary_watchdog_closes_only_its_exact_non_deployment_outcome(self):
        fixture, reader = self._watchdog_fixture(self.index)
        fixture["run"]["event"] = "push"
        endpoint = f"{reader.prefix}/actions/runs/20/attempts/1/jobs?per_page=100&page=1"
        jobs = reader.api.overrides[endpoint]["jobs"]
        jobs[0]["steps"].append({"name": "Await authenticated publication authority without deployment",
                                 "status": "completed", "conclusion": "success", "number": 4})
        decision = {"event": "push", "release": True, "no_release": False,
                    "reason": "release-diff-requires-full-lineage"}
        with patch.object(routing.release_routing, "git", return_value="d" * 40), \
                patch.object(routing.release_routing, "resolve_push", return_value=decision):
            result = routing.watchdog(root=ROOT, state_root=Path("/fixture"), run_id=20, reader=reader)
            self.assertEqual(result, {"no_release": False, "delegated": True, "effective_head": "f" * 40})
            self.mock_retained.assert_not_called()
            deployed = next(step for step in jobs[0]["steps"] if step["name"] == "Push synchronized deployment branch")
            deployed["conclusion"] = "success"
            with self.assertRaises(SystemExit):
                routing.watchdog(root=ROOT, state_root=Path("/fixture"), run_id=20, reader=reader)

    def test_downloaded_visual_attestation_must_match_exact_original_and_execution(self):
        payload = {"head_sha": self.expected["public_sha"], "release_id": self.expected["release_id"],
                   "core_execution": self.index, "workflow": {"repository": binding.WEB_REPOSITORY,
                   "run_id": "20", "run_attempt": "1"}}
        raw = binding.canonical_bytes(payload)
        with tempfile.TemporaryDirectory(prefix="visual-binding-") as directory:
            path = Path(directory) / "local-attestation.json"
            path.write_bytes(raw)
            routing.check_visual_attestation(path, expected_index=self.index, expected_sha256=binding.sha256(raw))
            path.write_bytes(raw + b"\n")
            with self.assertRaisesRegex(binding.ExecutionBindingError, "VISUAL_ATTESTATION_BYTES_MISMATCH"):
                routing.check_visual_attestation(path, expected_index=self.index, expected_sha256=binding.sha256(raw))
            crossed = deepcopy(self.expected)
            crossed["intent_id"] = "0" * 64
            other = binding.build_index(binding=crossed, run_id=20, run_attempt=1, workflow_head_sha="f" * 40)
            with self.assertRaisesRegex(binding.ExecutionBindingError, "VISUAL_ATTESTATION_EXECUTION_MISMATCH"):
                routing.check_visual_attestation(path, expected_index=other, expected_sha256=binding.sha256(path.read_bytes()))

    def test_alias_watchdog_requires_exact_durable_owner_and_skipped_deployment(self):
        alias = binding.build_index(binding=self.expected, run_id=21, run_attempt=1,
                                    workflow_head_sha="f" * 40, canonical=self.index["canonical"])
        _, reader = self._watchdog_fixture(alias)
        with self.assertRaisesRegex(binding.ExecutionBindingError, "DELEGATED_CERTIFICATION_MISSING"):
            routing.watchdog(root=ROOT, state_root=Path("/fixture"), run_id=21, reader=reader)
        self.mock_retained.return_value = {"index": self.index}
        value = routing.watchdog(root=ROOT, state_root=Path("/fixture"), run_id=21, reader=reader)
        self.assertTrue(value["delegated"])
        self.mock_retained.assert_called_with(Path("/fixture"), self.expected, self.index["canonical"])

    def test_workflow_keeps_existing_jobs_and_gates_all_deployment_on_publish(self):
        workflow = (ROOT / ".github/workflows/publish.yml").read_text()
        jobs = [line for line in workflow.splitlines() if line.startswith("  ") and not line.startswith("   ") and line.endswith(":")]
        self.assertIn("  sync-cloudflare:", jobs)
        self.assertIn("  production-smoke:", jobs)
        self.assertIn("  refresh-open-release-prs:", jobs)
        self.assertNotIn("schedule:", workflow)
        self.assertEqual(workflow.count("python app/scripts/verify_core_publication_bundle.py"), 2)
        self.assertEqual(workflow.count("name: " + binding.EMIT_STEP), 1)
        sync = workflow.split("  sync-cloudflare:", 1)[1].split("  production-smoke:", 1)[0]
        for name in routing.release_routing.DEPLOYMENT_STEPS:
            step = sync.split("      - name: " + name, 1)[1].split("      - name:", 1)[0]
            self.assertIn("steps.execution.outputs.action == 'publish'", step)
        self.assertIn('test "$(git rev-parse origin/main)" = "$CANDIDATE_SHA"', sync)
        chain = workflow.split("name: Certify exact source-to-production chain", 1)[1].split("      - name:", 1)[0]
        self.assertIn("--core-attestation /tmp/core-publication-lineage/attestation.json", chain)
        self.assertIn("--core-receipt /tmp/core-publication-lineage/receipt.json", chain)
        watchdog = (ROOT / ".github/workflows/production-certification-watchdog.yml").read_text()
        self.assertEqual(watchdog.count("steps.routing.outputs.delegated != 'true'"), 3)
        self.assertIn("steps.routing.outputs.effective_head", watchdog)


if __name__ == "__main__":
    unittest.main()
