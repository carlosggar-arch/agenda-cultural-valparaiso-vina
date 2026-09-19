"""Local snapshot-verification contracts; no remote signatures/publication.

GitHub metadata and subprocess probes below are explicit test doubles. The
overlay tests use real local Git repositories; no cultural HTTP or Git remote
writes are performed. Existing cryptographic tests own signature validation.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import publication_execution_binding as original
import publication_snapshot_verification as contract
import snapshot_verification_cli as cli
import snapshot_production_smoke as smoke
import production_release_attestation as attestation
import production_certification_history as history
from test_publication_execution_github import FixtureAPI, execution_fixture
import test_publication_execution_history as history_fixtures


def proof_fixture(index):
    runtime_release = "v999-" + "d" * 12
    return contract.validate({"contract": contract.CONTRACT, "version": contract.VERSION,
        "original_core_execution": deepcopy(index),
        "execution": {"run_id": 301, "run_attempt": 1, "workflow_head_sha": "8" * 40},
        "verifier": {"tree_sha": "9" * 40,
            "code_hashes": {path: f"{number:040x}" for number, path in enumerate(contract.CODE_PATHS, 1)}},
        "original_artifact": {"id": 401, "sha256": "a" * 64},
        "composition": {"contract": "historical-data-current-runtime-composition", "version": "1.0.0",
            "historical": {"head_sha": index["binding"]["public_sha"],
                "release_id": index["binding"]["release_id"], "tree_sha": "7" * 40},
            "runtime": {"head_sha": "8" * 40, "release_id": runtime_release, "tree_sha": "9" * 40},
            "preserved_blobs": {path: f"{number + 1000:040x}"
                for number, path in enumerate(contract.PRESERVED_SURFACES, 1)},
            "changed_paths": ["app/app.js", "app/data/release-bundle.json"]}})


def proof_metadata(proof):
    identity = proof["execution"]
    model = execution_fixture(original.build_index(binding=proof["original_core_execution"]["binding"],
        run_id=identity["run_id"], run_attempt=identity["run_attempt"], workflow_head_sha=identity["workflow_head_sha"]))
    model["run"].update(event="workflow_dispatch")
    model["job"].update(name=contract.VERIFY_JOB, steps=[
        {"name": name, "number": number, "status": "completed", "conclusion": "success"}
        for number, name in enumerate((contract.VERIFY_STEP, contract.EMIT_STEP), 1)])
    model["check"]["name"] = contract.VERIFY_JOB
    model["annotations"] = [{"title": contract.NOTICE_TITLE, "message": contract.encode_notice(proof),
                             "path": contract.WORKFLOW, "annotation_level": "notice"}]
    return {"run": model["run"], "job": model["job"], "check_run": model["check"],
            "annotations": model["annotations"], "workflow_id": 55}


class SnapshotVerificationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = history_fixtures.PublicationExecutionHistoryTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.proof = proof_fixture(self.fixture.index)
        self.metadata = proof_metadata(self.proof)

    def verify(self, *, proof=None, metadata=None, policy=None):
        value = proof or self.proof
        return contract.verify_github_proof(value,
            expected_binding=self.fixture.binding, approved_policy=policy or self.proof["verifier"],
            actual_policy=self.proof["verifier"], **(metadata or self.metadata))

    def test_exact_proof_keeps_historical_owner_and_new_verifier_distinct(self):
        self.assertEqual(self.verify(), self.proof)
        self.assertEqual(self.proof["original_core_execution"], self.fixture.index)
        self.assertNotEqual(self.proof["execution"]["run_id"], self.fixture.index["execution"]["run_id"])
        self.assertEqual(contract.decode_notice(contract.encode_notice(self.proof)),
                         contract.proof_notice(self.proof))

    def test_compact_notice_binds_large_proof_without_annotation_truncation(self):
        proof = deepcopy(self.proof)
        proof["composition"]["changed_paths"] = [f"app/generated/runtime-{number:04d}.js"
                                                  for number in range(500)]
        encoded = contract.encode_notice(proof)
        self.assertGreater(len(contract.encode(proof)), 4096)
        self.assertLessEqual(len(encoded), 2048)
        self.assertEqual(contract.decode_notice(encoded), contract.proof_notice(proof))
        self.assertEqual(contract.decode_notice(encoded)["repository"], original.WEB_REPOSITORY)
        crossed = contract.proof_notice(proof)
        crossed["repository"] = "other/repository"
        message = base64.b64encode(original.canonical_bytes(crossed)).decode("ascii")
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "NOTICE_REPOSITORY_INVALID"):
            contract.decode_notice(message)

    def test_new_proof_rejects_original_run_reuse_and_rerun(self):
        for key, value in (("run_id", 201), ("run_attempt", 2)):
            with self.subTest(key=key):
                proof = deepcopy(self.proof)
                proof["execution"][key] = value
                with self.assertRaises(contract.SnapshotVerificationError):
                    contract.validate(proof)

    def test_every_critical_blob_and_whole_tree_requires_independent_approval(self):
        for path in contract.CODE_PATHS:
            with self.subTest(path=path):
                policy = deepcopy(self.proof["verifier"])
                policy["code_hashes"][path] = "f" * 40
                with self.assertRaisesRegex(contract.SnapshotVerificationError, "UNAPPROVED_VERIFIER_CODE"):
                    self.verify(policy=policy)
        policy = deepcopy(self.proof["verifier"])
        policy["tree_sha"] = "f" * 40
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "UNAPPROVED_VERIFIER_CODE"):
            self.verify(policy=policy)

    def test_crossed_run_job_check_notice_and_failed_crypto_step_block(self):
        changes = (
            ("run", "run_attempt", 2), ("run", "head_sha", "f" * 40),
            ("run", "event", "repository_dispatch"), ("run", "repository", {"full_name": "wrong/repo"}),
            ("job", "run_id", 999), ("check_run", "app", {"id": 1, "slug": "github-actions"}),
            ("check_run", "details_url", "https://example.invalid/"),
        )
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                metadata = deepcopy(self.metadata)
                metadata[section][key] = value
                with self.assertRaises(contract.SnapshotVerificationError):
                    self.verify(metadata=metadata)
        for change in ("missing", "duplicate", "step", "order"):
            with self.subTest(change=change):
                metadata = deepcopy(self.metadata)
                if change == "missing": metadata["annotations"] = []
                elif change == "duplicate": metadata["annotations"] *= 2
                elif change == "step": metadata["job"]["steps"][0]["conclusion"] = "failure"
                else: metadata["job"]["steps"][1]["number"] = 1
                with self.assertRaises(contract.SnapshotVerificationError): self.verify(metadata=metadata)

    def test_watchdog_requires_same_proof_archive_and_actual_execution(self):
        value = contract.watchdog_notice(self.proof,
            execution_identity={"run_id": 302, "run_attempt": 1, "workflow_head_sha": "8" * 40},
            attestation_sha256="b" * 64, archive_sha256="c" * 64)
        metadata = proof_metadata({**self.proof, "execution": value["execution"]})
        metadata["run"].update(event="workflow_run", path=contract.WATCHDOG_WORKFLOW)
        metadata["job"].update(name=contract.WATCHDOG_JOB, steps=[
            {"name": contract.WATCHDOG_STEP, "number": 1, "status": "completed", "conclusion": "success"}])
        metadata["check_run"]["name"] = contract.WATCHDOG_JOB
        metadata["annotations"] = [{"title": contract.WATCHDOG_NOTICE,
            "path": contract.WATCHDOG_WORKFLOW, "annotation_level": "notice", "message": contract.encode_watchdog(value)}]
        args = dict(proof=self.proof, approved_policy=self.proof["verifier"], actual_policy=self.proof["verifier"],
                    attestation_sha256="b" * 64, archive_sha256="c" * 64, **metadata)
        self.assertEqual(contract.verify_watchdog(value, **args), value)
        for field in ("verification_sha256", "archive_sha256", "attestation_sha256", "binding_sha256"):
            with self.subTest(field=field):
                changed = deepcopy(value)
                changed[field] = "0" * 64
                with self.assertRaises(contract.SnapshotVerificationError): contract.verify_watchdog(changed, **args)

    def snapshot_payload(self):
        payload = deepcopy(self.fixture.payload)
        payload["snapshot_verification"] = self.proof
        payload["workflow"].update(run_id="301", run_attempt="1")
        payload["head_sha"] = self.proof["composition"]["runtime"]["head_sha"]
        payload["release_id"] = self.proof["composition"]["runtime"]["release_id"]
        payload["release"] = 999
        return payload

    def test_snapshot_history_retains_original_owner_and_is_byte_idempotent(self):
        payload = self.snapshot_payload()
        self.fixture.write_json(self.fixture.incoming, payload)
        archive, _, created = history.persist_certification(self.fixture.incoming, self.fixture.state)
        self.assertTrue(created)
        self.assertEqual(json.loads(archive.read_text())["core_execution"], self.fixture.index)
        before = self.fixture.files_under(self.fixture.state)
        self.assertFalse(history.persist_certification(self.fixture.incoming, self.fixture.state)[2])
        self.assertEqual(before, self.fixture.files_under(self.fixture.state))
        self.assertEqual(history.validate_history(self.fixture.state)["chain"]["length"], 1)

    def test_snapshot_history_rejects_replacement_verifier_or_original_owner(self):
        payload = self.snapshot_payload()
        self.fixture.write_json(self.fixture.incoming, payload)
        history.persist_certification(self.fixture.incoming, self.fixture.state)
        before = self.fixture.files_under(self.fixture.state)
        changed = deepcopy(payload)
        changed["snapshot_verification"]["execution"]["run_id"] += 1
        changed["workflow"]["run_id"] = "302"
        self.fixture.write_json(self.fixture.incoming, changed)
        with self.assertRaises(history.CertificationHistoryError):
            history.persist_certification(self.fixture.incoming, self.fixture.state)
        self.assertEqual(before, self.fixture.files_under(self.fixture.state))
        del changed["snapshot_verification"]
        with self.assertRaises(history.CertificationHistoryError): history.validated_core_execution(changed)

    def test_real_attestation_builder_retains_later_verifier_and_original_core_index(self):
        self.fixture.write_json(self.fixture.incoming, self.fixture.index)
        proof_path = self.root / "snapshot-verification.json"
        local_proof = deepcopy(self.proof)
        head, tree, runtime_release = "8" * 40, "9" * 40, "v300-" + "d" * 12
        local_proof["execution"]["workflow_head_sha"] = head
        local_proof["verifier"]["tree_sha"] = tree
        local_proof["composition"]["runtime"].update(
            head_sha=head, tree_sha=tree, release_id=runtime_release)
        self.fixture.write_json(proof_path, local_proof)
        with self.fixture.local_attestation_inputs(event="workflow_dispatch") as paths:
            with patch.dict(os.environ, {"GITHUB_RUN_ID": "301", "GITHUB_RUN_ATTEMPT": "1"}), \
                    patch.object(attestation, "git_head", return_value=head), \
                    patch.object(attestation, "release_bundle", return_value={
                        "release": 300, "release_id": runtime_release, "fingerprint": "1" * 64}):
                result = attestation.build_attestation(*paths, verify_network=False,
                    core_execution_index=self.fixture.incoming, snapshot_verification=proof_path)
        self.assertEqual(result["head_sha"], local_proof["composition"]["runtime"]["head_sha"])
        self.assertEqual(result["release_id"], local_proof["composition"]["runtime"]["release_id"])
        self.assertEqual(contract.validate_attestation(result), local_proof)
        self.assertEqual(result["core_execution"], self.fixture.index)
        self.assertEqual(result["workflow"]["run_id"], "301")

    def git(self, root, *args):
        return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-c", "user.name=Local Fixture",
            "-c", "user.email=fixture@example.invalid", *args], cwd=root, stderr=subprocess.PIPE).decode().strip()

    def repositories(self, label=""):
        base = self.root / label if label else self.root
        base.mkdir(parents=True, exist_ok=True)
        verifier, snapshot = base / "verifier", base / "snapshot"
        verifier.mkdir()
        self.git(verifier, "init")
        scripts = verifier / "app/scripts"
        scripts.mkdir(parents=True)
        for path in original.CODE_PATHS:
            target = verifier / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# LOCAL CODE IDENTITY FIXTURE - NOT EXECUTED\n")
        (scripts / "old.py").write_text("VALUE = 'old'\n")
        (verifier / "agenda_web.json").write_text('[{"fixture":"not-public-data"}]\n')
        (verifier / "app/data").mkdir(parents=True, exist_ok=True)
        (verifier / "app/data/release-bundle.json").write_text(json.dumps({"release_id": self.fixture.binding["release_id"]}) + "\n")
        for path in contract.PRESERVED_SURFACES:
            target = verifier / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_text('{"fixture":"preserved"}\n')
        self.git(verifier, "add", ".")
        self.git(verifier, "commit", "-m", "local parent fixture")
        (verifier / "agenda_web.json").write_text('[{"fixture":"not-public-data","snapshot":true}]\n')
        self.git(verifier, "add", ".")
        self.git(verifier, "commit", "-m", "local snapshot fixture")
        public = self.git(verifier, "rev-parse", "HEAD")
        self.git(self.root, "clone", "--no-hardlinks", str(verifier), str(snapshot))
        (scripts / "old.py").write_text("VALUE = 'reviewed'\n")
        (scripts / "new.py").write_text("NEW = 'reviewed'\n")
        (verifier / "app/data/release-bundle.json").write_text(
            json.dumps({"release_id": "v999-" + "d" * 12}) + "\n")
        self.git(verifier, "add", ".")
        self.git(verifier, "commit", "-m", "local verifier fixture")
        return snapshot, verifier, public, self.git(verifier, "rev-parse", "HEAD")

    def test_real_git_overlay_changes_only_verifier_bytes_and_preserves_snapshot_head(self):
        args = self.repositories()
        snapshot, verifier, public, _ = args
        before = (snapshot / "agenda_web.json").read_bytes()
        cli.install_verifier(*args)
        cli.require_overlay(*args)
        self.assertEqual(self.git(snapshot, "rev-parse", "HEAD"), public)
        self.assertEqual((snapshot / "agenda_web.json").read_bytes(), before)
        self.assertEqual((snapshot / "app/scripts/new.py").read_bytes(), (verifier / "app/scripts/new.py").read_bytes())

    def test_untracked_new_verifier_mutation_is_rejected(self):
        args = self.repositories()
        cli.install_verifier(*args)
        (args[0] / "app/scripts/new.py").write_text("UNAPPROVED = True\n")
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "UNAPPROVED_UNTRACKED_SCRIPT"):
            cli.require_overlay(*args)

    def test_changed_snapshot_data_or_extra_script_blocks(self):
        args = self.repositories()
        cli.install_verifier(*args)
        (args[0] / "agenda_web.json").write_text("[]")
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "NON_VERIFIER_BYTES"):
            cli.require_overlay(*args)
        (args[0] / "agenda_web.json").write_bytes((args[1] / "agenda_web.json").read_bytes())
        (args[0] / "app/scripts/injected.py").write_text("BAD = True\n")
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "UNAPPROVED_SCRIPT"):
            cli.require_overlay(*args)

    def test_historical_release_is_not_declared_equal_to_later_runtime(self):
        snapshot, verifier, public, runtime = self.repositories()
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "PUBLICATION_SURFACES_CHANGED"):
            cli.require_same_surfaces(verifier, public, runtime)
        composed = cli.build_runtime_composition(verifier, public, runtime)
        self.assertEqual(composed["historical"]["head_sha"], public)
        self.assertEqual(composed["runtime"]["head_sha"], runtime)
        self.assertNotEqual(composed["historical"]["release_id"], composed["runtime"]["release_id"])
        self.assertFalse(composed.get("historical_success_claimed", False))

    def test_runtime_composition_blocks_changed_data_and_unreviewed_media(self):
        for path in ("agenda_web.json", "assets/event-images/injected.webp"):
            with self.subTest(path=path):
                _snapshot, verifier, public, _runtime = self.repositories(path.replace("/", "-"))
                target = verifier / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"changed-data-or-media")
                self.git(verifier, "add", path)
                self.git(verifier, "commit", "-m", "untrusted composition fixture")
                runtime = self.git(verifier, "rev-parse", "HEAD")
                expected = "PRESERVED_SURFACE_CHANGED" if path == "agenda_web.json" else "PATH_NOT_RUNTIME_ONLY"
                with self.assertRaisesRegex(contract.SnapshotVerificationError, expected):
                    cli.build_runtime_composition(verifier, public, runtime)

    def artifact_fixture(self, members=None):
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            for name, raw in (members or {"receipt.json": b'{"fixture":"not-a-real-receipt"}\n'}).items():
                archive.writestr(name, raw)
        zipped = buffer.getvalue()
        run = {"id": 201, "run_attempt": 1, "head_sha": "c" * 40, "status": "completed",
               "run_started_at": "2026-09-12T12:00:00Z", "updated_at": "2026-09-12T12:10:00Z"}
        artifact = {"id": 401, "name": "local-original-201-1", "created_at": "2026-09-12T12:05:00Z",
                    "expired": False, "workflow_run": {"id": 201, "head_sha": "c" * 40},
                    "digest": "sha256:" + original.sha256(zipped)}
        rows = [artifact]
        reader = SimpleNamespace(prefix="repos/" + original.WEB_REPOSITORY, pages=lambda *_: deepcopy(rows))
        return reader, run, artifact, rows, zipped

    def test_artifact_zip_is_verified_and_preserved_without_modification(self):
        reader, run, artifact, _, raw = self.artifact_fixture()
        destination = self.root / "original"
        with patch.object(cli.subprocess, "check_output", return_value=raw) as download:
            result = cli.download_artifact(reader, run=run, name=artifact["name"], destination=destination)
        self.assertEqual(result, {"id": 401, "sha256": original.sha256(raw)})
        self.assertEqual((destination / "original.zip").read_bytes(), raw)
        self.assertIn("/actions/artifacts/401/zip", download.call_args.args[0][-1])

    def test_artifact_wrong_attempt_digest_or_duplicate_blocks(self):
        for mode in ("missing", "time", "digest", "duplicate", "run", "head", "expired"):
            with self.subTest(mode=mode):
                reader, run, artifact, rows, raw = self.artifact_fixture()
                if mode == "missing": rows.clear()
                elif mode == "time": artifact["created_at"] = "2026-09-12T11:00:00Z"
                elif mode == "digest": artifact["digest"] = "sha256:" + "0" * 64
                elif mode == "duplicate": rows.append(deepcopy(artifact))
                elif mode == "run": artifact["workflow_run"]["id"] = 999
                elif mode == "head": artifact["workflow_run"]["head_sha"] = "a" * 40
                else: artifact["expired"] = True
                with patch.object(cli.subprocess, "check_output", return_value=raw):
                    with self.assertRaises(contract.SnapshotVerificationError):
                        cli.download_artifact(reader, run=run, name=artifact["name"], destination=self.root / mode)

    def test_unsafe_archive_member_cannot_escape_diagnostic_directory(self):
        reader, run, artifact, _, raw = self.artifact_fixture({"../escaped.json": b"{}"})
        with patch.object(cli.subprocess, "check_output", return_value=raw):
            with self.assertRaisesRegex(contract.SnapshotVerificationError, "UNSAFE_ZIP_MEMBER"):
                cli.download_artifact(reader, run=run, name=artifact["name"], destination=self.root / "unsafe")
        self.assertFalse((self.root / "escaped.json").exists())

    def test_requested_original_attempt_cannot_mask_current_rerun(self):
        def api(path):
            if "/attempts/" in path: return {"id": 201, "run_attempt": 1, "status": "completed"}
            return {"id": 201, "run_attempt": 2, "status": "completed"}
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "RUN_ATTEMPT_ADVANCED"):
            cli.exact_run(SimpleNamespace(api=api, prefix="repos/example"), 201, 1)

    def test_prepare_uses_real_local_git_and_api_contract_with_explicit_crypto_double(self):
        snapshot, verifier, public, _ = self.repositories()
        for path in contract.CODE_PATHS:
            target = verifier / path
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# LOCAL REVIEWED VERIFIER FIXTURE - NOT EXECUTED\n")
        self.git(verifier, "add", ".")
        self.git(verifier, "commit", "-m", "complete local verifier identity fixture")
        verifier_sha = self.git(verifier, "rev-parse", "HEAD")
        parent = self.git(verifier, "rev-parse", public + "^")
        receipt, signed = b'{"fixture":"unsigned-local-receipt"}\n', b'{"fixture":"not-a-signature"}\n'
        release = (snapshot / "app/data/release-bundle.json").read_bytes()
        claim = {"contract": "core-publication-finalizer-lineage", "core_sha": "a" * 40,
            "intent_id": "b" * 64, "publisher": {"run_id": 101, "run_attempt": 1},
            "finalizer": {"run_id": 102, "run_attempt": 2}, "public": {"sha": public, "parent_sha": parent},
            "release_id": self.fixture.binding["release_id"], "acquisition_shas": {"valpo": "e" * 40},
            "receipt_sha256": original.sha256(receipt), "release_bundle_sha256": original.sha256(release),
            "pre_write_acquisition_fence": {"fixture": "not-actual-fence"}}
        lineage = original.canonical_bytes(claim)
        expected = original.binding_from_verified_bytes(lineage=lineage, receipt=receipt,
            release_bundle=release, sigstore_bundle=signed)
        index = original.build_index(binding=expected, run_id=201, run_attempt=1, workflow_head_sha=public)
        source = execution_fixture(index)
        source["run"].update(conclusion="failure", updated_at="2026-09-12T12:10:00Z")
        source["job"]["conclusion"] = "failure"
        api = FixtureAPI(source)
        prefix = "repos/" + original.WEB_REPOSITORY
        members = {"core-execution.json": original.canonical_bytes(index),
                   "core-publication-lineage/attestation.json": lineage,
                   "core-publication-lineage/receipt.json": receipt,
                   "core-publication-lineage/bundle.json": signed}
        _, _, artifact, _, zipped = self.artifact_fixture(members)
        artifact.update(name="publication-release-decision-201-1", workflow_run={"id": 201, "head_sha": public})
        api.overrides[f"{prefix}/actions/runs/201/artifacts?per_page=100&page=1"] = {"total_count": 1, "artifacts": [artifact]}
        api.overrides[f"{prefix}/git/ref/heads/main"] = {"object": {"sha": verifier_sha}}
        reader = cli.GithubReader(api=api, code_resolver=lambda sha, paths: {
            path: self.git(verifier, "rev-parse", f"{sha}:{path}") for path in paths})
        args = SimpleNamespace(snapshot=snapshot, verifier=verifier, public_sha=public,
            original_run_id=201, original_run_attempt=1, output=self.root / "prepared")
        real_command = subprocess.check_output
        def local_command(command, *positional, **kwargs):
            if command[:2] == ["gh", "api"]:
                self.assertTrue(command[-1].endswith("/actions/artifacts/401/zip"))
                return zipped
            self.assertEqual(command[0], "git")
            return real_command(command, *positional, **kwargs)
        def crypto_double(**kwargs):
            payload = kwargs["event"]["client_payload"]
            self.assertEqual(kwargs["expected_public_sha"], public)
            import base64
            self.assertEqual(base64.b64decode(payload["attestation_base64"]), lineage)
            self.assertEqual(base64.b64decode(payload["receipt_base64"]), receipt)
            self.assertEqual(base64.b64decode(payload["sigstore_bundle_base64"]), signed)
        environment = {"GITHUB_RUN_ID": "301", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": verifier_sha,
                       "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
                       "GITHUB_REPOSITORY": original.WEB_REPOSITORY}
        with patch.dict(os.environ, environment), patch.object(cli, "verify_event", side_effect=crypto_double) as verify:
            with patch.object(cli.subprocess, "check_output", side_effect=local_command):
                result = cli.prepare(args, reader)
        verify.assert_called_once()
        self.assertEqual(result["original_core_execution"], index)
        self.assertEqual(result["execution"]["workflow_head_sha"], verifier_sha)
        self.assertEqual((args.output / "original/original.zip").read_bytes(), zipped)
        self.assertEqual(self.git(snapshot, "rev-parse", "HEAD"), public)
        self.assertEqual(source["run"]["conclusion"], "failure")
        args.output = self.root / "invalid-signature"
        with patch.dict(os.environ, environment), patch.object(cli, "verify_event", side_effect=RuntimeError("INVALID_SIGNATURE")):
            with patch.object(cli.subprocess, "check_output", side_effect=local_command):
                with self.assertRaisesRegex(RuntimeError, "INVALID_SIGNATURE"):
                    cli.prepare(args, reader)
        self.assertFalse((args.output / "snapshot-verification.json").exists())

    def test_prepare_rejects_wrong_repository_branch_event_or_attempt_before_reading(self):
        environment = {"GITHUB_RUN_ID": "301", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "8" * 40,
                       "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
                       "GITHUB_REPOSITORY": original.WEB_REPOSITORY}
        args = SimpleNamespace(public_sha="c" * 40, original_run_id=201, original_run_attempt=1)
        for key, value in (("GITHUB_REF", "refs/heads/untrusted"), ("GITHUB_REPOSITORY", "other/repo"),
                           ("GITHUB_EVENT_NAME", "push"), ("GITHUB_RUN_ATTEMPT", "2")):
            with self.subTest(key=key), patch.dict(os.environ, {**environment, key: value}):
                with self.assertRaisesRegex(contract.SnapshotVerificationError, "NEW_EXPLICIT_EXECUTION_REQUIRED"):
                    cli.prepare(args, SimpleNamespace())

    def test_watchdog_cli_verifies_artifacts_history_original_bytes_and_exact_callback(self):
        # Complete CLI wiring: real ZIP transport checks, metadata validators,
        # binding calculation and history persistence. Only network, Git policy
        # identity and crypto are explicit local doubles (never live evidence).
        release = original.canonical_bytes({"release_id": self.fixture.binding["release_id"]})
        receipt = b'{"fixture":"unsigned-local-receipt"}\n'
        signed = b'{"fixture":"not-a-signature"}\n'
        claim = {"contract": "core-publication-finalizer-lineage", "core_sha": "a" * 40,
            "intent_id": "b" * 64, "publisher": {"run_id": 101, "run_attempt": 1},
            "finalizer": {"run_id": 102, "run_attempt": 2},
            "public": {"sha": "c" * 40, "parent_sha": "d" * 40},
            "release_id": self.fixture.binding["release_id"], "acquisition_shas": {"valpo": "e" * 40},
            "receipt_sha256": original.sha256(receipt), "release_bundle_sha256": original.sha256(release),
            "pre_write_acquisition_fence": {"fixture": "not-actual-fence"}}
        lineage = original.canonical_bytes(claim)
        expected = original.binding_from_verified_bytes(lineage=lineage, receipt=receipt,
            release_bundle=release, sigstore_bundle=signed)
        old_index = original.build_index(binding=expected, run_id=201, run_attempt=1, workflow_head_sha="c" * 40)
        original_members = {"core-execution.json": original.canonical_bytes(old_index),
            "core-publication-lineage/attestation.json": lineage,
            "core-publication-lineage/receipt.json": receipt,
            "core-publication-lineage/bundle.json": signed}
        _, _, old_artifact, _, original_zip = self.artifact_fixture(original_members)
        old_artifact.update(name="publication-release-decision-201-1")
        proof = proof_fixture(old_index)
        proof["original_artifact"] = {"id": old_artifact["id"], "sha256": original.sha256(original_zip)}
        metadata = proof_metadata(proof)
        source = {"run": metadata["run"], "job": metadata["job"],
                  "check": metadata["check_run"], "annotations": metadata["annotations"]}
        source["run"]["updated_at"] = "2026-09-12T12:10:00Z"
        old_source = execution_fixture(old_index)
        old_source["run"].update(conclusion="failure", updated_at="2026-09-12T12:10:00Z")
        old_source["job"]["conclusion"] = "failure"
        api = FixtureAPI(old_source, source)
        prefix = "repos/" + original.WEB_REPOSITORY
        jobs = [source["job"], {**source["job"], "id": 3011, "name": contract.SMOKE_JOB}]
        jobs.extend({"name": name, "conclusion": "skipped"} for name in
                    ("sync-cloudflare", "production-smoke", "refresh-open-release-prs"))
        api.overrides[f"{prefix}/actions/runs/301/attempts/1/jobs?per_page=100&page=1"] = {
            "total_count": len(jobs), "jobs": jobs}
        api.overrides[f"{prefix}/git/commits/" + "8" * 40] = {
            "sha": "8" * 40, "tree": {"sha": proof["verifier"]["tree_sha"]}}
        api.overrides[f"{prefix}/git/ref/heads/main"] = {"object": {"sha": "8" * 40}}
        api.overrides[f"{prefix}/actions/runs/201/artifacts?per_page=100&page=1"] = {
            "total_count": 1, "artifacts": [old_artifact]}
        _, _, verification_artifact, _, verification_zip = self.artifact_fixture({
            "snapshot-verification.json": original.canonical_bytes(proof)})
        verification_artifact.update(id=450, name="snapshot-verification-301-1",
                                     workflow_run={"id": 301, "head_sha": "8" * 40})
        api.overrides[f"{prefix}/actions/runs/301/artifacts?per_page=100&page=1"] = {
            "total_count": 1, "artifacts": [verification_artifact]}
        reader = cli.GithubReader(api=api, code_resolver=lambda sha, paths: {
            path: proof["verifier"]["code_hashes"][path] if sha == "8" * 40 else "9" * 40 for path in paths})
        payload = self.snapshot_payload()
        payload.update(core_execution=old_index, snapshot_verification=proof)
        payload["workflow"].update(run_id="301", run_attempt="1")
        self.fixture.write_json(self.fixture.incoming, payload)
        archive_path, _, _ = history.persist_certification(self.fixture.incoming, self.fixture.state)
        payload_bytes = self.fixture.incoming.read_bytes()
        state_before = self.fixture.files_under(self.fixture.state)
        snapshot, verifier = self.root / "snapshot", self.root / "verifier"
        (snapshot / "app/data").mkdir(parents=True)
        (snapshot / "app/data/release-bundle.json").write_bytes(release)
        event_path = self.root / "event.json"
        self.fixture.write_json(event_path, {"workflow_run": source["run"]})
        production_members = {"production-release-attestation.json": payload_bytes,
            **{"original/extracted/" + name: raw for name, raw in original_members.items()}}
        def production_archive():
            _, _, artifact, _, raw = self.artifact_fixture(production_members)
            artifact.update(id=501, name="snapshot-production-verification-301-1",
                            workflow_run={"id": 301, "head_sha": "8" * 40})
            api.overrides[f"{prefix}/actions/runs/301/artifacts?per_page=100&page=1"] = {
                "total_count": 2, "artifacts": [verification_artifact, artifact]}
            return raw
        zipped = production_archive()
        def transport(command, **kwargs):
            self.assertEqual(command[:2], ["gh", "api"])
            if command[-1].endswith("/actions/artifacts/401/zip"): return original_zip
            if command[-1].endswith("/actions/artifacts/450/zip"): return verification_zip
            self.assertTrue(command[-1].endswith("/actions/artifacts/501/zip"))
            return zipped
        def git_identity(root, *arguments):
            if arguments == ("rev-parse", "HEAD"):
                return (("c" if root == snapshot else "8") * 40 + "\n").encode()
            self.assertEqual(arguments[:2], ("diff", "--name-only"))
            return b"app/scripts/snapshot_verification_cli.py\n"
        def crypto_double(**kwargs):
            import base64
            self.assertEqual(kwargs["expected_public_sha"], expected["public_sha"])
            self.assertEqual(base64.b64decode(kwargs["event"]["client_payload"]["sigstore_bundle_base64"]), signed)
        env = {"GITHUB_RUN_ID": "302", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "8" * 40,
               "GITHUB_EVENT_NAME": "workflow_run", "GITHUB_EVENT_PATH": str(event_path)}
        def invoke(label):
            args = SimpleNamespace(source_run_id=301, verifier=verifier, snapshot=snapshot,
                output=self.root / label, state_root=self.fixture.state,
                github_output=self.root / (label + "-outputs"))
            with patch.dict(os.environ, env), patch.object(cli, "git", side_effect=git_identity), \
                 patch.object(cli, "local_policy", return_value=proof["verifier"]), \
                 patch.object(cli, "require_runtime_composition", return_value=proof["composition"]), \
                 patch.object(cli, "verify_event", side_effect=crypto_double) as crypto, \
                 patch.object(cli.subprocess, "check_output", side_effect=transport):
                notice = cli.verify_watchdog(args, reader)
            crypto.assert_called_once()
            return args, notice
        args, notice = invoke("watchdog-ok")
        self.assertEqual(notice["verification"], {"run_id": 301, "run_attempt": 1})
        self.assertEqual(notice["execution"]["run_id"], 302)
        self.assertEqual(notice["binding_sha256"], old_index["binding_sha256"])
        self.assertEqual(notice["attestation_sha256"], original.sha256(payload_bytes))
        self.assertEqual(notice["archive_sha256"], original.sha256(archive_path.read_bytes()))
        self.assertEqual(args.github_output.read_text().splitlines(), ["finalizer_run_id=102",
            "finalizer_run_attempt=2", "intent_id=" + "b" * 64,
            "verification_run_id=301", "verification_run_attempt=1"])
        self.assertEqual((args.output / "original-check/original.zip").read_bytes(), original_zip)
        self.assertEqual(invoke("watchdog-repeat")[1], notice)
        self.assertEqual(self.fixture.files_under(self.fixture.state), state_before)
        original_verification_zip = verification_zip
        original_verification_digest = verification_artifact["digest"]
        changed_proof = deepcopy(proof)
        changed_proof["composition"]["changed_paths"].append("app/tampered-after-notice.js")
        _, _, changed_artifact, _, verification_zip = self.artifact_fixture({
            "snapshot-verification.json": original.canonical_bytes(changed_proof)})
        verification_artifact["digest"] = changed_artifact["digest"]
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "NOTICE_PROOF_MISMATCH"):
            invoke("changed-proof-after-notice")
        verification_zip = original_verification_zip
        verification_artifact["digest"] = original_verification_digest
        original_state = self.fixture.state
        self.fixture.state = self.root / "crossed-history"
        crossed = deepcopy(payload)
        crossed["snapshot_verification"]["verifier"]["tree_sha"] = "f" * 40
        crossed["snapshot_verification"]["composition"]["runtime"]["tree_sha"] = "f" * 40
        self.fixture.write_json(self.fixture.incoming, crossed)
        history.persist_certification(self.fixture.incoming, self.fixture.state)
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "DURABLE_CERTIFICATE_MISMATCH"):
            invoke("crossed-durable-archive")
        self.fixture.state = original_state
        production_members["production-release-attestation.json"] = payload_bytes + b"\n"
        zipped = production_archive()
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "DURABLE_CERTIFICATE_MISMATCH"):
            invoke("changed-payload-bytes")
        production_members["production-release-attestation.json"] = payload_bytes
        zipped = production_archive()
        original_zip += b"changed-archive-envelope"
        old_artifact["digest"] = "sha256:" + original.sha256(original_zip)
        api.overrides[f"{prefix}/actions/runs/201/artifacts?per_page=100&page=1"]["artifacts"] = [old_artifact]
        with self.assertRaisesRegex(contract.SnapshotVerificationError, "HISTORICAL_ARTIFACT_CHANGED"):
            invoke("changed-original-archive")
        self.assertEqual(self.fixture.files_under(self.fixture.state), state_before)

    def test_probe_failure_is_terminal_and_never_converted_to_success(self):
        def fail(command, **kwargs):
            kwargs["stdout"].write(b"EXPLICIT LOCAL FAILED PROBE\n")
            return subprocess.CompletedProcess(command, 3)
        with patch.object(smoke.subprocess, "run", side_effect=fail):
            with self.assertRaisesRegex(contract.SnapshotVerificationError, "PROBE_FAILED"):
                smoke.run(self.root, self.root, "deployment_readiness.py", "probe.log")

    def test_all_probe_groups_run_without_publication_or_acquisition(self):
        calls = []
        def local_probe(snapshot, evidence, script, log, arguments=()):
            calls.append((script, arguments))
            marker = "PRODUCTION_SERIES_CONTRACTS_VERIFIED " if log == "series.log" else "PRODUCTION_ADMIN_STAGING_VERIFIED "
            (evidence / log).write_text(marker + "LOCAL FIXTURE\n")
        with patch.object(smoke, "run", side_effect=local_probe): smoke.run_groups(self.root, self.root)
        scripts = {name for name, _ in calls}
        self.assertEqual(scripts, {"production_admin_staging_smoke.py", "production_series_contract.py",
            "production_browser_selenium_smoke.py", "production_warm_start_smoke.py", "test_web_pwa_visibility_parity.py"})
        self.assertTrue(any(name == "test_web_pwa_visibility_parity.py" and "--production" in args for name, args in calls))

    def test_failed_group_blocks_without_suppressing_other_results(self):
        calls = []
        def local_probe(snapshot, evidence, script, log, arguments=()):
            calls.append(script)
            raise RuntimeError("EXPLICIT LOCAL PROBE FAILURE")
        with patch.object(smoke, "run", side_effect=local_probe):
            with self.assertRaisesRegex(contract.SnapshotVerificationError, "PRODUCTION_PROBES_FAILED"):
                smoke.run_groups(self.root, self.root)
        self.assertEqual(len(calls), 4)


def run_contract():
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(SnapshotVerificationTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    return {"tests": result.testsRun, "successful": True}


if __name__ == "__main__":
    run_contract()
