"""Offline GitHub shape fixtures: no claim of live signature or API execution."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import publication_execution_binding as binding
from publication_execution_github import GithubReader, github_api


def example_binding():
    return {"core_sha": "a" * 40, "intent_id": "b" * 64,
            "publisher": {"run_id": 10, "run_attempt": 1},
            "finalizer": {"run_id": 11, "run_attempt": 1},
            "public_sha": "c" * 40, "parent_sha": "d" * 40,
            "release_id": "v300-111111111111", "acquisition_shas": {"valpo": "e" * 40},
            **{name: str(number) * 64 for number, name in enumerate((
                "fence_sha256", "lineage_sha256", "receipt_sha256",
                "release_bundle_sha256", "sigstore_bundle_sha256"), 1)}}


def execution_fixture(index):
    rid, attempt = binding.run_key(index["execution"])
    head = index["execution"]["workflow_head_sha"]
    api = "https://api.github.com/repos/" + binding.WEB_REPOSITORY
    html = "https://github.com/" + binding.WEB_REPOSITORY
    run = {"id": rid, "run_attempt": attempt, "head_sha": head, "head_branch": "main",
           "repository": {"full_name": binding.WEB_REPOSITORY},
           "head_repository": {"full_name": binding.WEB_REPOSITORY},
           "workflow_id": 55, "path": binding.WORKFLOW, "event": "repository_dispatch",
           "url": f"{api}/actions/runs/{rid}", "html_url": f"{html}/actions/runs/{rid}",
           "created_at": "2026-09-12T12:00:01Z", "run_started_at": "2026-09-12T12:00:02Z",
           "status": "completed", "conclusion": "success"}
    job = {"id": rid * 10, "run_id": rid, "run_attempt": attempt, "head_sha": head,
           "name": "sync-cloudflare", "status": "completed", "conclusion": "success",
           "run_url": run["url"], "check_run_url": f"{api}/check-runs/{rid * 10}",
           "html_url": f"{html}/actions/runs/{rid}/job/{rid * 10}",
           "steps": [{"name": name, "status": "completed", "conclusion": "success", "number": n}
                     for n, name in enumerate((binding.VERIFY_STEP, binding.EMIT_STEP), 1)]}
    check = {"id": rid * 10, "url": job["check_run_url"], "head_sha": head,
             "name": job["name"], "details_url": job["html_url"],
             "app": {"id": 15368, "slug": "github-actions"}}
    annotations = [{"title": binding.NOTICE_TITLE, "message": binding.encode_notice(index),
                    "path": binding.WORKFLOW, "annotation_level": "notice"}]
    return {"run": run, "job": job, "check": check, "annotations": annotations}


class FixtureAPI:
    def __init__(self, *fixtures):
        self.fixtures = {value["run"]["id"]: value for value in fixtures}
        self.listed = [deepcopy(value["run"]) for value in fixtures]
        self.calls = []
        self.overrides = {}

    def __call__(self, endpoint):
        self.calls.append(endpoint)
        if endpoint in self.overrides:
            return deepcopy(self.overrides[endpoint])
        route = endpoint.split("?", 1)[0]
        query = parse_qs(urlparse(endpoint).query)
        if route.endswith("/workflows/publish.yml"):
            return {"id": 55, "path": binding.WORKFLOW}
        if route.endswith("/workflows/55/runs"):
            assert query["event"] == ["repository_dispatch"]
            assert "head_sha" not in query
            page = int(query["page"][0])
            return {"total_count": len(self.listed), "workflow_runs": deepcopy(self.listed[(page - 1) * 100:page * 100])}
        if "/check-runs/" in route:
            cid = int(route.split("/check-runs/")[1].split("/")[0])
            value = next(row for row in self.fixtures.values() if row["check"]["id"] == cid)
            return deepcopy(value["annotations"] if route.endswith("/annotations") else value["check"])
        if "/actions/runs/" in route:
            rid = int(route.split("/actions/runs/")[1].split("/")[0])
            value = self.fixtures[rid]
            if route.endswith("/jobs"):
                return {"total_count": 1, "jobs": [deepcopy(value["job"])]}
            return deepcopy(value["run"])
        raise AssertionError("Unexpected API read: " + endpoint)


class PublicationExecutionGithubTests(unittest.TestCase):
    def setUp(self):
        self.expected = example_binding()
        self.index = binding.build_index(binding=self.expected, run_id=20, run_attempt=1,
                                         workflow_head_sha="f" * 40)
        self.fixture = execution_fixture(self.index)
        self.api = FixtureAPI(self.fixture)
        self.reader = GithubReader(api=self.api, code_resolver=lambda sha, paths: {path: "9" * 40 for path in paths})

    def observe(self):
        return self.reader.observations(self.expected, "2026-09-12T12:00:00Z")

    def test_exact_index_and_late_workflow_head_with_same_code(self):
        found = self.observe()
        self.assertNotEqual(self.index["execution"]["workflow_head_sha"], self.expected["public_sha"])
        self.assertEqual(found["verified"][0]["index"], self.index)
        self.assertEqual(found["pending"], [])
        self.assertEqual(found["suspect"], [])

    def test_failed_canonical_is_preserved_not_replaced_by_green(self):
        self.fixture["run"]["conclusion"] = "failure"
        self.fixture["job"]["conclusion"] = "failure"
        found = self.observe()
        self.assertEqual(found["verified"][0]["run"]["conclusion"], "failure")
        self.assertEqual(binding.select_root([item["index"] for item in found["verified"]], expected_binding=self.expected), self.index)

    def test_missing_active_proof_is_pending(self):
        self.fixture["annotations"] = []
        self.fixture["run"]["status"] = "in_progress"
        self.assertEqual(len(self.observe()["pending"]), 1)

    def test_missing_terminal_proof_is_suspect(self):
        self.fixture["annotations"] = []
        self.assertEqual(len(self.observe()["suspect"]), 1)

    def test_emitter_not_finished_never_claims_verified(self):
        self.fixture["job"]["steps"][1]["status"] = "in_progress"
        found = self.observe()
        self.assertFalse(found["verified"])
        self.assertEqual(len(found["pending"]), 1)

    def test_failed_signature_step_never_becomes_authority(self):
        self.fixture["job"]["steps"][0]["conclusion"] = "failure"
        with self.assertRaisesRegex(binding.ExecutionBindingError, "STEP_NOT_VERIFIED"):
            self.observe()

    def test_new_attempt_between_listing_and_read_blocks(self):
        self.fixture["run"]["run_attempt"] = 2
        with self.assertRaisesRegex(binding.ExecutionBindingError, "ATTEMPT_MOVED"):
            self.observe()

    def test_api_pagination_preserves_all_101_results(self):
        rows = [execution_fixture(binding.build_index(binding=self.expected, run_id=n, run_attempt=1,
                                                     workflow_head_sha="f" * 40)) for n in range(100, 201)]
        api = FixtureAPI(*rows)
        reader = GithubReader(api=api, code_resolver=self.reader.code_resolver)
        found = reader.observations(self.expected, "2026-09-12T12:00:00Z")
        self.assertEqual(len(found["verified"]), 101)
        self.assertTrue(any("page=2" in call for call in api.calls))
        with self.assertRaisesRegex(binding.ExecutionBindingError, "CONTRADICTORY_ROOTS"):
            binding.select_root([item["index"] for item in found["verified"]], expected_binding=self.expected)

    def test_pagination_count_moving_or_incomplete_blocks(self):
        for second_count in (99, 101):
            calls = 0
            def fake(endpoint):
                nonlocal calls
                calls += 1
                return {"total_count": 101 if calls == 1 else second_count,
                        "items": [0] * 100 if calls == 1 else []}
            with self.subTest(count=second_count), self.assertRaises(binding.ExecutionBindingError):
                GithubReader(api=fake).pages("x", "items")

    def test_other_verified_publication_is_ignored_but_not_unproven(self):
        other = deepcopy(self.expected)
        other["public_sha"] = "0" * 40
        self.fixture["annotations"][0]["message"] = binding.encode_notice(binding.build_index(
            binding=other, run_id=20, run_attempt=1, workflow_head_sha="f" * 40))
        self.assertEqual(self.observe(), {"verified": [], "pending": [], "suspect": [], "unstarted": []})

    def test_crossed_binding_for_same_public_commit_blocks(self):
        other = deepcopy(self.expected)
        other["intent_id"] = "0" * 64
        self.fixture["annotations"][0]["message"] = binding.encode_notice(binding.build_index(
            binding=other, run_id=20, run_attempt=1, workflow_head_sha="f" * 40))
        with self.assertRaisesRegex(binding.ExecutionBindingError, "BINDING_MISMATCH"):
            self.observe()

    def test_changed_authority_code_blocks_late_callback(self):
        self.reader.code_resolver = lambda sha, paths: {path: ("8" if sha == "f" * 40 else "9") * 40 for path in paths}
        with self.assertRaisesRegex(binding.ExecutionBindingError, "UNAUTHORISED_WORKFLOW_CODE"):
            self.observe()

    def test_changed_checked_out_candidate_code_blocks_even_with_trusted_workflow(self):
        self.reader.code_resolver = lambda sha, paths: {path: ("8" if sha == self.expected["public_sha"] else "9") * 40 for path in paths}
        with self.assertRaisesRegex(binding.ExecutionBindingError, "UNAUTHORISED_CANDIDATE_CODE"):
            self.observe()

    def test_duplicate_or_crossed_check_notice_blocks(self):
        self.fixture["annotations"] *= 2
        with self.assertRaisesRegex(binding.ExecutionBindingError, "CONTRADICTORY_NOTICES"):
            self.observe()

    def test_current_run_excluded_without_mutating_metadata(self):
        before = deepcopy(self.api.listed)
        self.assertFalse(self.reader.observations(self.expected, "2026-09-12T12:00:00Z", exclude_run=20)["verified"])
        self.assertEqual(self.api.listed, before)

    def test_queued_unstarted_delivery_cannot_block_current_root(self):
        for state in ("queued", "pending", "requested", "waiting"):
            with self.subTest(state=state):
                self.fixture["run"].update(status=state, conclusion=None)
                self.fixture["job"].update(status=state, conclusion=None, steps=[], started_at=None)
                self.fixture["annotations"] = []
                found = self.observe()
                self.assertEqual(len(found["unstarted"]), 1)
                self.assertFalse(found["pending"] or found["suspect"] or found["verified"])

    def test_queue_rerun_and_cancelled_unproven_delivery_remain_blocking(self):
        self.fixture["annotations"] = []
        self.fixture["job"].update(status="queued", conclusion=None, steps=[], started_at=None)
        self.fixture["run"].update(status="pending", conclusion=None, run_attempt=2)
        self.api.listed[0]["run_attempt"] = 2
        found = self.observe()
        self.assertFalse(found["unstarted"])
        self.assertEqual(len(found["pending"]), 1)
        self.fixture["run"].update(status="completed", conclusion="cancelled")
        found = self.observe()
        self.assertFalse(found["unstarted"])
        self.assertEqual(len(found["suspect"]), 1)

    def test_queued_with_prior_activity_is_not_ignored(self):
        self.fixture["run"]["status"] = "queued"
        self.fixture["annotations"] = []
        found = self.observe()
        self.assertFalse(found["unstarted"])
        self.assertEqual(len(found["pending"]), 1)

    def test_public_tree_requires_all_exact_blobs(self):
        complete = {"truncated": False, "tree": [{"path": path, "type": "blob", "sha": "9" * 40} for path in binding.CODE_PATHS]}
        reader = GithubReader(api=lambda endpoint: complete)
        self.assertEqual(set(reader.code_hashes("a" * 40)), set(binding.CODE_PATHS))
        complete["tree"].pop()
        with self.assertRaisesRegex(binding.ExecutionBindingError, "CODE_PATH_MISSING"):
            reader.code_hashes("b" * 40)

    def test_permission_error_no_artifact_or_opaque_fallback(self):
        with patch("publication_execution_github.subprocess.check_output", side_effect=RuntimeError("403")) as command:
            with self.assertRaisesRegex(RuntimeError, "403"):
                github_api("repos/example")
        command.assert_called_once_with(["gh", "api", "repos/example"], timeout=30)


if __name__ == "__main__":
    unittest.main()
