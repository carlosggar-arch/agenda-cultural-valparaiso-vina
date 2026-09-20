"""Offline recovery-authority regressions; no remote certification is claimed."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import post_write_recovery_authority as recovery
import publication_execution_binding as binding


def run(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def prior_fixture():
    head = "7" * 40
    record = {
        "id": 55, "run_attempt": 1, "status": "completed", "conclusion": "failure",
        "path": binding.WORKFLOW, "event": "repository_dispatch", "head_branch": "main",
        "head_sha": head, "repository": {"full_name": binding.WEB_REPOSITORY},
        "head_repository": {"full_name": binding.WEB_REPOSITORY},
    }
    steps = [
        {"name": binding.VERIFY_STEP, "status": "completed", "conclusion": "success"},
        {"name": "Preserve Core lineage transport evidence", "status": "completed", "conclusion": "success"},
        {"name": binding.EMIT_STEP, "status": "completed", "conclusion": "failure"},
    ]
    for name in (
        "Create exact-tree handoff preserving deployment history",
        "Require exact deployment-branch parity with candidate",
        "Validate Cloudflare build snapshot and exact release lineage",
        "Push synchronized deployment branch",
        "Fast-close changed dataset freshness and identity",
        "Fast-close deterministic runtime contracts",
        "Wait once for both production origins in parallel",
        "Mark byte deployment, pending visual verification",
    ):
        steps.append({"name": name, "status": "completed", "conclusion": "skipped"})
    jobs = {"jobs": [
        {"name": "sync-cloudflare", "run_id": 55, "run_attempt": 1, "head_sha": head,
         "status": "completed", "conclusion": "failure", "steps": steps},
        {"name": "production-smoke", "status": "completed", "conclusion": "skipped"},
        {"name": "refresh-open-release-prs", "status": "completed", "conclusion": "skipped"},
    ]}
    prior = {
        "repository": binding.WEB_REPOSITORY, "workflow": binding.WORKFLOW,
        "run_id": 55, "run_attempt": 1, "workflow_head_sha": head,
        "disposition": recovery.DISPOSITION,
        "run_sha256": recovery.sha256(recovery.canonical_bytes(record)),
        "jobs_sha256": recovery.sha256(recovery.canonical_bytes(jobs)),
    }
    return record, jobs, prior


class RecoveryAuthorityTests(unittest.TestCase):
    def test_failed_delivery_disposition_requires_no_index_boundary_or_deployment(self):
        record, jobs, prior = prior_fixture()
        self.assertEqual(recovery.validate_prior_metadata(prior=prior, run=record, jobs=jobs), prior)
        for step, conclusion in ((binding.EMIT_STEP, "success"),
                                 ("Push synchronized deployment branch", "success")):
            crossed = deepcopy(jobs)
            next(row for row in crossed["jobs"][0]["steps"] if row["name"] == step)["conclusion"] = conclusion
            changed = dict(prior, jobs_sha256=recovery.sha256(recovery.canonical_bytes(crossed)))
            with self.subTest(step=step), self.assertRaises(recovery.RecoveryAuthorityError):
                recovery.validate_prior_metadata(prior=changed, run=record, jobs=crossed)

    def make_repository(self) -> tuple[tempfile.TemporaryDirectory, Path, str]:
        temp = tempfile.TemporaryDirectory(prefix="recovery-runtime-")
        root = Path(temp.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "fixture"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=root, check=True)
        files = set(binding.CODE_PATHS) | {
            "agenda_web.json", "app/data/gijon/agenda_web.json", "fuentes_publicas.json",
            "app/data/source-registry.json", "app/data/quality/source-coverage.json",
            "app/data/quality/event-quality.json", "app/data/quality/release-readiness.json",
            "app/data/venue-registry.json", "app/data/release-bundle.json",
            "app/data/release-provenance.json", "app/service-worker-assets.generated.js",
            "index.html", "manifest.webmanifest", "app/index.html", "app/manifest.webmanifest",
        }
        for name in files:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"fixture": name}) + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "historical"], cwd=root, check=True)
        historical = run(root, "rev-parse", "HEAD")
        (root / ".github/workflows/publish.yml").write_text("name: approved recovery verifier\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "runtime"], cwd=root, check=True)
        return temp, root, historical

    def runtime(self, root: Path) -> dict:
        head = run(root, "rev-parse", "HEAD")
        hashes = {path: run(root, "rev-parse", f"{head}:{path}") for path in binding.CODE_PATHS}
        return {
            "head_sha": head, "tree_sha": run(root, "show", "-s", "--format=%T", head),
            "code_hashes_sha256": recovery.sha256(recovery.canonical_bytes(hashes)),
            "policy_sha256": "9" * 64,
        }

    def test_current_runtime_composition_preserves_all_public_surfaces(self):
        temp, root, historical = self.make_repository()
        self.addCleanup(temp.cleanup)
        result = recovery.runtime_composition(root, historical_sha=historical, runtime=self.runtime(root))
        self.assertEqual(result["historical_sha"], historical)
        self.assertEqual(result["changed_paths"], [".github/workflows/publish.yml"])

    def test_dataset_page_asset_or_release_change_is_never_runtime_compatibility(self):
        for path in ("agenda_web.json", "index.html", "app/service-worker-assets.generated.js",
                     "app/data/release-bundle.json"):
            temp, root, historical = self.make_repository()
            try:
                target = root / path
                target.write_text("changed\n", encoding="utf-8")
                subprocess.run(["git", "add", path], cwd=root, check=True)
                subprocess.run(["git", "commit", "-qm", "unauthorised surface"], cwd=root, check=True)
                with self.subTest(path=path), self.assertRaises(recovery.RecoveryAuthorityError):
                    recovery.runtime_composition(root, historical_sha=historical, runtime=self.runtime(root))
            finally:
                temp.cleanup()


if __name__ == "__main__":
    unittest.main()
