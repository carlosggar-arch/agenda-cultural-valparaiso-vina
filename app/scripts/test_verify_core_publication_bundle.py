"""Consumer unit/contract tests. gh signature results are explicitly modeled.

These tests exercise dispatch parsing, exact gh policy invocation, checked
certificate output and the real semantic lineage validator. They do NOT claim
to perform real Sigstore signing or cryptographic verification; retained
official fixtures and real-gh checks are separate evidence.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request
import zipfile

from core_publication_lineage import CoreLineageError, canonical_hash
from test_core_publication_lineage import evidence
import verify_core_publication_bundle as consumer


def encoded(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


class BundleConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.lineage, self.receipt = evidence(self.root)
        self.bundle = (b'{"dsseEnvelope":{"payloadType":"application/vnd.in-toto+json"},'
                       b'"fixture":"modeled CLI output, not a cryptographic signature"}\n')
        self.raw = json.dumps(self.lineage, sort_keys=True).encode()
        self.payload = {
            "public_sha": "c" * 40, "attestation_base64": encoded(self.raw),
            "attestation_sha256": hashlib.sha256(self.raw).hexdigest(),
            "receipt_base64": encoded(self.receipt),
            "lineage_transport": consumer.LINEAGE_TRANSPORT,
            "sigstore_bundle_base64": encoded(self.bundle),
        }
        self.certificate = {
            "issuer": consumer.OIDC_ISSUER,
            "subjectAlternativeName": consumer.SIGNER_IDENTITY,
            "sourceRepositoryURI": consumer.CORE_URI,
            "sourceRepositoryDigest": "a" * 40,
            "sourceRepositoryRef": "refs/heads/main",
            "sourceRepositoryVisibilityAtSigning": "private",
            "buildSignerURI": consumer.SIGNER_IDENTITY,
            "buildSignerDigest": "a" * 40,
            "buildTrigger": "workflow_dispatch",
            "runInvocationURI": consumer.CORE_URI + "/actions/runs/22/attempts/1",
            "runnerEnvironment": "github-hosted",
        }
        self.verified = [{"verificationResult": {
            "signature": {"certificate": self.certificate},
            "verifiedTimestamps": [{"fixture": "modeled verified TSA result"}],
            "statement": {"predicate": {"fixture": "never treated as signer authority"}},
        }}]

    def run_consumer(self, *, payload=None, verified=None, returncode=0, expected=None):
        process = subprocess.CompletedProcess(
            [], returncode, json.dumps(self.verified if verified is None else verified).encode(), b"modeled gh stderr",
        )
        with patch.object(consumer.subprocess, "run", return_value=process) as called, patch(
            "core_publication_lineage.subprocess.check_output", side_effect=["b" * 40 + "\n", "1\n"],
        ):
            try:
                return consumer.verify_event(
                    event={"client_payload": self.payload if payload is None else payload},
                    expected_public_sha=expected or "c" * 40, repository=self.root,
                    output_dir=self.root / "proof",
                )
            finally:
                self.calls = called.call_args_list

    def reference_payload(self, *, bundle=None):
        bundle = self.bundle if bundle is None else bundle
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("attestation.json", self.raw)
            archive.writestr("receipt.json", self.receipt)
            archive.writestr("bundle.sigstore.json", bundle)
        payload = {
            "public_sha": "c" * 40,
            "lineage_transport": consumer.LINEAGE_REFERENCE_TRANSPORT,
            "artifact_repository": consumer.CORE_REPOSITORY,
            "artifact_run_id": 22,
            "artifact_run_attempt": 1,
            "artifact_id": 901,
            "artifact_name": "publication-lineage-11-22-1",
            "artifact_digest": "sha256:" + "d" * 64,
            "attestation_sha256": hashlib.sha256(self.raw).hexdigest(),
            "receipt_sha256": hashlib.sha256(self.receipt).hexdigest(),
            "sigstore_bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        }
        artifact = {
            "id": 901, "name": payload["artifact_name"], "expired": False,
            "digest": payload["artifact_digest"], "workflow_run": {"id": 22},
        }
        run = {
            "id": 22, "run_attempt": 1, "repository": {"full_name": consumer.CORE_REPOSITORY},
            "path": consumer.FINALIZER_WORKFLOW, "event": "workflow_dispatch", "head_branch": "main",
            "head_sha": "a" * 40, "status": "in_progress", "conclusion": None,
        }
        return payload, artifact, run, archive_bytes.getvalue()

    def run_reference(self, *, payload=None, artifact=None, run=None, archive=None, request_error=None):
        defaults = self.reference_payload()
        payload = defaults[0] if payload is None else payload
        artifact = defaults[1] if artifact is None else artifact
        run = defaults[2] if run is None else run
        archive = defaults[3] if archive is None else archive
        process = subprocess.CompletedProcess([], 0, json.dumps(self.verified).encode(), b"")
        side_effect = request_error or [artifact, run, archive]
        with patch.object(consumer, "_request", side_effect=side_effect) as requested, patch.object(
            consumer.subprocess, "run", return_value=process,
        ) as called, patch(
            "core_publication_lineage.subprocess.check_output", side_effect=["b" * 40 + "\n", "1\n"],
        ):
            try:
                return consumer.verify_event(
                    event={"client_payload": payload}, expected_public_sha="c" * 40,
                    repository=self.root, output_dir=self.root / "proof-reference", artifact_token="token",
                )
            finally:
                self.reference_requests = requested.call_args_list
                self.calls = called.call_args_list

    def test_modern_strict_policy_and_exact_original_bytes(self):
        result = self.run_consumer()
        self.assertEqual(result["transport"], consumer.LINEAGE_TRANSPORT)
        command = self.calls[0].args[0]
        for flag, value in {
            "--bundle": str(self.root / "proof/bundle.json"), "--repo": consumer.CORE_REPOSITORY,
            "--cert-identity": consumer.SIGNER_IDENTITY, "--cert-oidc-issuer": consumer.OIDC_ISSUER,
            "--source-digest": "a" * 40, "--signer-digest": "a" * 40,
            "--source-ref": "refs/heads/main", "--format": "json",
        }.items():
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn("--deny-self-hosted-runners", command)
        self.assertIn("--no-public-good", command)
        self.assertNotIn("--custom-trusted-root", command)
        self.assertEqual((self.root / "proof/attestation.json").read_bytes(), self.raw)
        self.assertEqual((self.root / "proof/receipt.json").read_bytes(), self.receipt)
        self.assertEqual((self.root / "proof/bundle.json").read_bytes(), self.bundle)
        self.assertEqual(json.loads((self.root / "proof/verification.json").read_bytes()), self.verified)

    def test_reference_transport_downloads_large_exact_proof_from_in_progress_run(self):
        large_bundle = (b'{"dsseEnvelope":{"payloadType":"application/vnd.in-toto+json"},'
                        b'"padding":"' + b"x" * 102309 + b'"}\n')
        payload, artifact, run, archive = self.reference_payload(bundle=large_bundle)
        result = self.run_reference(payload=payload, artifact=artifact, run=run, archive=archive)
        self.assertEqual(result["transport"], consumer.LINEAGE_REFERENCE_TRANSPORT)
        self.assertLess(len(json.dumps({"event_type": "core_publication_lineage", "client_payload": payload})), 2048)
        self.assertGreater(len(large_bundle), 102309)
        proof = self.root / "proof-reference"
        self.assertEqual((proof / "attestation.json").read_bytes(), self.raw)
        self.assertEqual((proof / "receipt.json").read_bytes(), self.receipt)
        self.assertEqual((proof / "bundle.json").read_bytes(), large_bundle)
        self.assertEqual(len(self.reference_requests), 3)

    def test_cross_origin_artifact_redirect_does_not_leak_github_credentials(self):
        request = Request(
            "https://api.github.com/repos/example/private/actions/artifacts/901/zip",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer secret-token",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "agenda-core-lineage-verifier",
            },
        )
        redirected = consumer._ScopedCredentialRedirectHandler().redirect_request(
            request, None, 302, "Found", {},
            "https://results.blob.core.windows.net/actions-results/proof.zip?sig=signed",
        )
        self.assertIsNotNone(redirected)
        self.assertEqual(redirected.full_url, "https://results.blob.core.windows.net/actions-results/proof.zip?sig=signed")
        headers = {key.casefold(): value for key, value in redirected.header_items()}
        self.assertNotIn("authorization", headers)
        self.assertEqual(headers["user-agent"], "agenda-core-lineage-verifier")

    def test_same_origin_redirect_retains_github_credentials_and_insecure_redirect_blocks(self):
        request = Request(
            "https://api.github.com/repos/example/private/actions/artifacts/901/zip",
            headers={"Authorization": "Bearer secret-token", "X-GitHub-Api-Version": "2022-11-28"},
        )
        redirected = consumer._ScopedCredentialRedirectHandler().redirect_request(
            request, None, 302, "Found", {}, "https://api.github.com/signed/archive",
        )
        headers = {key.casefold(): value for key, value in redirected.header_items()}
        self.assertEqual(headers["authorization"], "Bearer secret-token")
        with self.assertRaisesRegex(consumer.BundleVerificationError, "ARTIFACT_REDIRECT_INVALID"):
            consumer._ScopedCredentialRedirectHandler().redirect_request(
                request, None, 302, "Found", {}, "http://results.example/proof.zip",
            )

    def test_reference_transport_rejects_missing_substituted_or_crossed_artifact(self):
        payload, artifact, run, archive = self.reference_payload()
        with self.assertRaisesRegex(consumer.BundleVerificationError, "DOWNLOAD_FAILED"):
            self.run_reference(payload=payload, request_error=consumer.BundleVerificationError(
                "CORE_LINEAGE_BUNDLE_ARTIFACT_DOWNLOAD_FAILED"
            ))
        crossed = deepcopy(artifact); crossed["name"] = "publication-lineage-99-22-1"
        with self.assertRaisesRegex(consumer.BundleVerificationError, "ARTIFACT_NAME_MISMATCH"):
            self.run_reference(payload=payload, artifact=crossed, run=run, archive=archive)
        crossed = deepcopy(run); crossed["repository"]["full_name"] = "attacker/other"
        with self.assertRaisesRegex(consumer.BundleVerificationError, "ARTIFACT_REPOSITORY_MISMATCH"):
            self.run_reference(payload=payload, artifact=artifact, run=crossed, archive=archive)
        crossed = deepcopy(run); crossed["run_attempt"] = 2
        with self.assertRaisesRegex(consumer.BundleVerificationError, "ARTIFACT_ATTEMPT_MISMATCH"):
            self.run_reference(payload=payload, artifact=artifact, run=crossed, archive=archive)
        changed = bytearray(archive); changed[-20] ^= 1
        with self.assertRaises(consumer.BundleVerificationError):
            self.run_reference(payload=payload, artifact=artifact, run=run, archive=bytes(changed))

    def test_cli_preserves_structured_failure_before_artifact_download(self):
        event = self.root / "event.json"
        event.write_text(json.dumps({"client_payload": {
            "public_sha": "c" * 40,
            "lineage_transport": consumer.LINEAGE_REFERENCE_TRANSPORT,
        }}), encoding="utf-8")
        output = self.root / "blocked-proof"
        argv = ["verify_core_publication_bundle.py", "--event", str(event),
                "--expected-public-sha", "c" * 40, "--repository", str(self.root),
                "--output-dir", str(output)]
        with patch.object(sys, "argv", argv):
            self.assertEqual(consumer.main(), 2)
        result = json.loads((output / "transport-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "blocked")
        self.assertIn("PAYLOAD_FIELDS_INVALID", result["error"])

    def test_legacy_uses_real_api_verifier_policy_not_missing_bundle_as_proof(self):
        legacy = {key: value for key, value in self.payload.items() if key in consumer.LEGACY_FIELDS}
        self.assertEqual(self.run_consumer(payload=legacy)["transport"], "legacy-github-attestation-api")
        command = self.calls[0].args[0]
        self.assertIn("--signer-workflow", command)
        self.assertNotIn("--bundle", command)
        with self.assertRaisesRegex(consumer.BundleVerificationError, "CRYPTOGRAPHIC_VERIFICATION_FAILED"):
            self.run_consumer(payload=legacy, returncode=1)

    def test_cli_failure_is_terminal_without_legacy_fallback(self):
        with self.assertRaisesRegex(consumer.BundleVerificationError, "CRYPTOGRAPHIC_VERIFICATION_FAILED"):
            self.run_consumer(returncode=1)
        self.assertEqual(len(self.calls), 1)
        self.assertIn("--bundle", self.calls[0].args[0])

    def test_verifier_unavailable_blocks_without_semantic_success(self):
        with patch.object(consumer.subprocess, "run", side_effect=FileNotFoundError("gh")) as called:
            with self.assertRaisesRegex(consumer.BundleVerificationError, "VERIFIER_UNAVAILABLE"):
                consumer.verify_event(event={"client_payload": self.payload}, expected_public_sha="c" * 40,
                                      repository=self.root, output_dir=self.root / "proof")
        called.assert_called_once()
        self.assertFalse((self.root / "proof/verification.json").exists())

    def test_duplicate_evidence_fields_and_malformed_verified_output_block(self):
        for raw in (b'{"client_payload":{},"client_payload":{}}', b'{"run_id":22,"run_id":23}'):
            with self.assertRaisesRegex(consumer.BundleVerificationError, "DUPLICATE_JSON_FIELD"):
                consumer.parse_json(raw)
        process = subprocess.CompletedProcess([], 0, b"not verified JSON", b"")
        with patch.object(consumer.subprocess, "run", return_value=process):
            with self.assertRaisesRegex(consumer.BundleVerificationError, "JSON_INVALID"):
                consumer.verify_event(event={"client_payload": self.payload}, expected_public_sha="c" * 40,
                                      repository=self.root, output_dir=self.root / "proof")
        self.assertFalse((self.root / "proof/verification.json").exists())

    def test_partial_unknown_and_null_transport_block_before_verification(self):
        mutations = [{"lineage_transport": None}, {"lineage_transport": ""},
                     {"lineage_transport": "untrusted"}, {"sigstore_bundle_base64": ""},
                     {"sigstore_bundle_base64": "not-base64"}, {"trusted_root": "attacker-root"}]
        payloads = [dict(self.payload, **mutation) for mutation in mutations]
        for field in ("lineage_transport", "sigstore_bundle_base64"):
            bad = deepcopy(self.payload)
            bad.pop(field)
            payloads.append(bad)
        for bad in payloads:
            with self.subTest(payload=bad), self.assertRaises(consumer.BundleVerificationError):
                self.run_consumer(payload=bad)
            self.assertEqual(self.calls, [])

    def test_dsse_nonliteral_payload_type_blocks_before_cli(self):
        literal = "application/vnd.in-toto+json"
        for value in (None, "text/plain", literal + " ", "".join(chr(ord(char) + 0x100) for char in literal)):
            envelope = {"dsseEnvelope": {"payloadType": value}}
            changed = dict(self.payload, sigstore_bundle_base64=encoded(json.dumps(envelope).encode()))
            with self.subTest(payload_type=value), self.assertRaisesRegex(consumer.BundleVerificationError, "DSSE_PAYLOAD_TYPE_INVALID"):
                self.run_consumer(payload=changed)
            self.assertEqual(self.calls, [])

    def test_crossed_certificate_identity_ref_attempt_and_runner_block(self):
        for key in self.certificate:
            bad = deepcopy(self.verified)
            bad[0]["verificationResult"]["signature"]["certificate"][key] = "wrong"
            with self.subTest(field=key), self.assertRaisesRegex(consumer.BundleVerificationError, "CERTIFICATE_IDENTITY_MISMATCH"):
                self.run_consumer(verified=bad)

    def test_unverified_predicate_cannot_substitute_for_certificate_or_timestamp(self):
        for field in ("signature", "verifiedTimestamps"):
            bad = deepcopy(self.verified)
            bad[0]["verificationResult"].pop(field)
            bad[0]["verificationResult"]["statement"]["predicate"].update(self.certificate)
            with self.subTest(field=field), self.assertRaises(consumer.BundleVerificationError):
                self.run_consumer(verified=bad)

    def test_ambiguous_or_empty_verifier_output_blocks(self):
        for result in ([], {}, [self.verified[0], self.verified[0]]):
            with self.subTest(result=result), self.assertRaises(consumer.BundleVerificationError):
                self.run_consumer(verified=result)

    def test_crossed_raw_bytes_and_public_sha_block(self):
        changed = dict(self.payload, attestation_base64=encoded(self.raw + b" "))
        with self.assertRaisesRegex(consumer.BundleVerificationError, "CONTENT_HASH_MISMATCH"):
            self.run_consumer(payload=changed)
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(consumer.BundleVerificationError, "PUBLIC_SHA_MISMATCH"):
            self.run_consumer(expected="d" * 40)

    def test_valid_signature_does_not_override_crossed_receipt_or_bundle(self):
        changed = dict(self.payload, receipt_base64=encoded(b"{}"))
        with self.assertRaisesRegex(CoreLineageError, "RECEIPT_HASH_INVALID"):
            self.run_consumer(payload=changed)
        bad_lineage = deepcopy(self.lineage)
        bad_lineage["release_bundle_sha256"] = "f" * 64
        bad_lineage["attestation_sha256"] = canonical_hash(bad_lineage)
        raw = json.dumps(bad_lineage).encode()
        changed = dict(self.payload, attestation_base64=encoded(raw), attestation_sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(CoreLineageError, "BUNDLE_HASH_INVALID"):
            self.run_consumer(payload=changed)

    def test_identical_replay_has_identical_outputs_and_no_dispatch(self):
        first = self.run_consumer()
        files = {path.name: path.read_bytes() for path in (self.root / "proof").iterdir()}
        self.assertEqual(first, self.run_consumer())
        self.assertEqual(files, {path.name: path.read_bytes() for path in (self.root / "proof").iterdir()})
        self.assertEqual(self.calls[0].args[0][:3], ["gh", "attestation", "verify"])

    def test_workflow_both_jobs_authenticate_before_writes_and_semantic_validation_remains(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/publish.yml").read_text()
        self.assertEqual(workflow.count("python app/scripts/verify_core_publication_bundle.py"), 2)
        self.assertEqual(workflow.count('--event "$GITHUB_EVENT_PATH"'), 2)
        self.assertEqual(workflow.count("permission-actions: read"), 2)
        self.assertEqual(workflow.count("repositories: agenda-cultural-core"), 2)
        self.assertEqual(workflow.count("CORE_ARTIFACT_TOKEN: ${{ steps.core-artifact-token.outputs.token }}"), 2)
        self.assertNotIn("permission-actions: write", workflow)
        self.assertNotIn("gh attestation verify", workflow)
        self.assertLess(workflow.index("python app/scripts/verify_core_publication_bundle.py"),
                        workflow.index("git push origin HEAD:cloudflare-preview"))
        # Authentication still runs in both jobs. The same original inputs
        # now reach all three semantic closes, including the final chain.
        self.assertEqual(workflow.count("--core-attestation /tmp/core-publication-lineage/attestation.json"), 3)
        self.assertEqual(workflow.count("--core-receipt /tmp/core-publication-lineage/receipt.json"), 3)
        close = workflow.split("name: Certify exact source-to-production chain", 1)[1].split("      - name:", 1)[0]
        self.assertIn("--core-attestation /tmp/core-publication-lineage/attestation.json", close)
        self.assertIn("--core-receipt /tmp/core-publication-lineage/receipt.json", close)
        self.assertIn("cp -R /tmp/core-publication-lineage /tmp/production-release-verification/core-publication-lineage", workflow)
        self.assertIn("path: /tmp/production-release-verification/", workflow)


if __name__ == "__main__":
    unittest.main()
