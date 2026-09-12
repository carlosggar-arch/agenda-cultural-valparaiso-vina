"""Read-only public GitHub execution indices, shared by Core and Web.

No artifact download, credential minting, polling or ownership selection lives
here. A successful run without a verified binding is not publication evidence.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
from urllib.parse import quote

try:
    from . import publication_execution_binding as binding_contract
except ImportError:
    import publication_execution_binding as binding_contract


CODE_PATHS = binding_contract.CODE_PATHS
UNSTARTED_STATUSES = {"queued", "pending", "requested", "waiting"}


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise binding_contract.ExecutionBindingError("CORE_EXECUTION_TIMESTAMP_INVALID") from exc
    binding_contract.require(result.tzinfo is not None, "TIMESTAMP_TIMEZONE_MISSING")
    return result


def github_api(endpoint: str):
    return binding_contract.parse_json(subprocess.check_output(["gh", "api", endpoint], timeout=30))


class GithubReader:
    def __init__(self, root: Path | None = None, *, api=None, code_resolver=None):
        self.root = root
        self.api = api or github_api
        self.code_resolver = code_resolver or self._public_code_hashes
        self.repository = binding_contract.WEB_REPOSITORY
        self.prefix = "repos/" + self.repository
        self._code_cache = {}

    def pages(self, endpoint: str, key: str | None = None) -> list:
        result, declared = [], None
        separator = "&" if "?" in endpoint else "?"
        for page in range(1, 1001):
            payload = self.api(f"{endpoint}{separator}per_page=100&page={page}")
            if key is None:
                binding_contract.require(isinstance(payload, list), "PAGE_SHAPE_INVALID")
                rows = payload
            else:
                binding_contract.require(isinstance(payload, dict) and isinstance(payload.get(key), list), "PAGE_SHAPE_INVALID")
                count = payload.get("total_count")
                binding_contract.require(type(count) is int and count >= 0, "PAGE_COUNT_INVALID")
                if declared is None:
                    declared = count
                binding_contract.require(count == declared, "PAGE_COUNT_MOVED")
                rows = payload[key]
            result.extend(rows)
            if len(rows) < 100:
                break
        else:
            raise binding_contract.ExecutionBindingError("CORE_EXECUTION_PAGE_LIMIT_REACHED")
        if declared is not None:
            binding_contract.require(len(result) == declared, "PAGES_INCOMPLETE")
        return result

    def _public_code_hashes(self, sha: str, paths: tuple[str, ...]) -> dict:
        # Git object IDs from the public tree bind exact source bytes without
        # requiring a Web checkout or cross-repository artifact credentials.
        tree = self.api(f"{self.prefix}/git/trees/{sha}?recursive=1")
        binding_contract.require(isinstance(tree, dict) and tree.get("truncated") is False
                                 and isinstance(tree.get("tree"), list), "CODE_TREE_INCOMPLETE")
        rows = tree["tree"]
        selected = {row.get("path"): row.get("sha") for row in rows
                    if row.get("path") in paths and row.get("type") == "blob"}
        binding_contract.require(set(selected) == set(paths), "CODE_PATH_MISSING")
        return selected

    def code_hashes(self, sha: str) -> dict:
        if sha not in self._code_cache:
            self._code_cache[sha] = self.code_resolver(sha, CODE_PATHS)
        return self._code_cache[sha]

    def observations(self, expected_binding: dict, not_before: str, exclude_run=None) -> dict:
        binding_contract.validate_binding(expected_binding)
        lower = timestamp(not_before)
        workflow = self.api(f"{self.prefix}/actions/workflows/publish.yml")
        binding_contract.require(isinstance(workflow, dict) and type(workflow.get("id")) is int
                                 and workflow.get("path") == binding_contract.WORKFLOW, "WORKFLOW_INVALID")
        created = quote(">=" + not_before, safe="")
        listed = self.pages(f"{self.prefix}/actions/workflows/{workflow['id']}/runs?event=repository_dispatch&created={created}", "workflow_runs")
        ids = [run.get("id") for run in listed]
        binding_contract.require(len(set(ids)) == len(ids), "DUPLICATE_RUN_PAGE")
        output = {"verified": [], "pending": [], "suspect": [], "unstarted": []}
        for snapshot in listed:
            binding_contract.require(type(snapshot.get("id")) is int, "RUN_ID_INVALID")
            if timestamp(snapshot.get("created_at")) < lower:
                continue
            if exclude_run is not None and snapshot["id"] == exclude_run:
                continue
            run = self.api(f"{self.prefix}/actions/runs/{snapshot['id']}")
            binding_contract.require(run.get("id") == snapshot["id"]
                                     and run.get("run_attempt") == snapshot.get("run_attempt")
                                     and run.get("run_started_at") == snapshot.get("run_started_at"), "ATTEMPT_MOVED")
            binding_contract.require(run.get("event") == "repository_dispatch"
                                     and run.get("path") == binding_contract.WORKFLOW
                                     and run.get("workflow_id") == workflow["id"], "RUN_WORKFLOW_INVALID")
            jobs = self.pages(f"{self.prefix}/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs")
            # The existing global concurrency lock permits later callbacks to
            # wait here. They cannot have claimed authority or deployed yet.
            # Do not confuse an unstarted delivery with a missing prior proof.
            if (run.get("status") in UNSTARTED_STATUSES and run.get("run_attempt") == 1
                    and run.get("conclusion") is None
                    and all(job.get("status") in UNSTARTED_STATUSES and not job.get("started_at")
                            and job.get("conclusion") is None
                            and all(step.get("status") in UNSTARTED_STATUSES and not step.get("started_at")
                                    and step.get("conclusion") is None for step in job.get("steps", []))
                            for job in jobs)):
                output["unstarted"].append({"run": run, "reason": "delivery-not-started"})
                continue
            candidates = [job for job in jobs if job.get("name") == "sync-cloudflare"]
            binding_contract.require(len({job["name"] for job in candidates}) == len(candidates), "DUPLICATE_JOB")
            found, related, waiting = False, False, False
            for job in candidates:
                if job.get("conclusion") == "skipped":
                    continue
                check_url = job.get("check_run_url", "")
                expected_prefix = "https://api.github.com/" + self.prefix + "/check-runs/"
                binding_contract.require(isinstance(check_url, str) and check_url.startswith(expected_prefix)
                                         and check_url.removeprefix(expected_prefix).isdigit(), "CHECK_URL_INVALID")
                endpoint = check_url.removeprefix("https://api.github.com/")
                check = self.api(endpoint)
                annotations = self.pages(endpoint + "/annotations")
                markers = [value for value in annotations if value.get("title") == binding_contract.NOTICE_TITLE]
                binding_contract.require(len(markers) <= 1, "CONTRADICTORY_NOTICES")
                if not markers:
                    continue
                index = binding_contract.parse_notice(markers[0].get("message"))
                steps = {step.get("name"): step for step in job.get("steps", [])}
                if any(steps.get(name, {}).get("status") != "completed"
                       for name in (binding_contract.VERIFY_STEP, binding_contract.EMIT_STEP)):
                    waiting = True
                    continue
                actual_binding = index["binding"]
                expected_code = self.code_hashes(actual_binding["parent_sha"])
                binding_contract.require(self.code_hashes(actual_binding["public_sha"]) == expected_code,
                                         "UNAUTHORISED_CANDIDATE_CODE")
                binding_contract.verify_github_index(
                    index, run=run, job=job, check_run=check, annotations=annotations,
                    expected_binding=actual_binding, workflow_id=workflow["id"],
                    expected_code_hashes=expected_code,
                    actual_code_hashes=self.code_hashes(run["head_sha"]),
                )
                found = True
                if actual_binding["public_sha"] != expected_binding["public_sha"]:
                    continue
                binding_contract.validate_index(index, expected_binding=expected_binding)
                related = True
                output["verified"].append({"index": index, "run": run, "job": job})
            if not found or waiting:
                name = "pending" if run.get("status") != "completed" or waiting else "suspect"
                output[name].append({"run": run, "reason": "execution-proof-not-yet-verifiable" if name == "pending" else "execution-proof-missing"})
            elif related:
                # A verified failed canonical run remains visible in verified;
                # callers must use its actual conclusion, never another green.
                pass
        return output
