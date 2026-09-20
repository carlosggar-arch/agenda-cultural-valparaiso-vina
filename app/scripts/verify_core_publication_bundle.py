"""Authenticate Core lineage before either Web deployment path can write.

Hashes bind exact transported bytes; they do not establish signer authority.
The installed official gh verifier owns signature, root, timestamp and artifact
verification. This module then checks authenticated certificate identity and the
existing receipt/Git/release contract. It never signs or dispatches anything.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

from core_publication_lineage import (
    CANONICAL_WRITER, CORE_REPOSITORY, CoreLineageError, validate as validate_core_lineage,
)

# The Core writer reads this literal capability from its immutable Web baseline.
LINEAGE_TRANSPORT = "github-sigstore-bundle-v1"
LINEAGE_REFERENCE_TRANSPORT = "github-actions-artifact-sigstore-bundle-v2"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
CORE_URI = "https://github.com/" + CORE_REPOSITORY
SIGNER_IDENTITY = CORE_URI + "/" + CANONICAL_WRITER + "@refs/heads/main"
LEGACY_FIELDS = {"public_sha", "attestation_base64", "attestation_sha256", "receipt_base64"}
BUNDLE_FIELDS = LEGACY_FIELDS | {"lineage_transport", "sigstore_bundle_base64"}
REFERENCE_IDENTITY_FIELDS = {
    "public_sha", "lineage_transport", "artifact_repository", "artifact_run_id",
    "artifact_run_attempt", "artifact_id", "artifact_name", "artifact_digest",
}
REFERENCE_LEGACY_FIELDS = REFERENCE_IDENTITY_FIELDS | {
    "attestation_sha256", "receipt_sha256", "sigstore_bundle_sha256",
}
REFERENCE_FIELDS = REFERENCE_IDENTITY_FIELDS | {"content_hashes"}
REFERENCE_HASH_FIELDS = {"attestation", "receipt", "sigstore_bundle"}
FINALIZER_WORKFLOW = ".github/workflows/finalize-public-agenda.yml"
PROOF_FILES = {
    "attestation": "attestation.json",
    "receipt": "receipt.json",
    "bundle": "bundle.sigstore.json",
}


class BundleVerificationError(RuntimeError):
    pass


class _ScopedCredentialRedirectHandler(HTTPRedirectHandler):
    """Keep the GitHub bearer token on GitHub, never on its signed blob URL."""

    def redirect_request(self, request, fp, code, msg, headers, new_url):
        redirected = super().redirect_request(request, fp, code, msg, headers, new_url)
        if redirected is None:
            return None
        source = urlsplit(request.full_url)
        target = urlsplit(new_url)
        require(target.scheme == "https" and bool(target.hostname), "ARTIFACT_REDIRECT_INVALID")
        if (source.scheme.casefold(), (source.hostname or "").casefold()) != (
            target.scheme.casefold(), (target.hostname or "").casefold()
        ):
            # The artifact REST endpoint returns a short-lived signed storage
            # URL.  Forwarding GitHub's bearer token makes Azure treat the
            # request as OAuth instead of SAS and fail with HTTP 401.  The SAS
            # query authenticates the exact immutable archive by itself.
            redirected.remove_header("Authorization")
        return redirected


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise BundleVerificationError("CORE_LINEAGE_BUNDLE_" + reason)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, "DUPLICATE_JSON_FIELD")
        value[key] = item
    return value


def parse_json(raw: bytes | str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError) as exc:
        raise BundleVerificationError("CORE_LINEAGE_BUNDLE_JSON_INVALID") from exc


def decode_field(payload: dict[str, Any], name: str) -> bytes:
    value = payload.get(name)
    require(isinstance(value, str) and bool(value), "ENCODING_INVALID:" + name)
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise BundleVerificationError("CORE_LINEAGE_BUNDLE_ENCODING_INVALID:" + name) from exc


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _request(url: str, token: str, *, json_response: bool) -> Any:
    require(bool(token), "ARTIFACT_TOKEN_MISSING")
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "agenda-core-lineage-verifier",
    })
    try:
        with build_opener(_ScopedCredentialRedirectHandler()).open(request, timeout=30) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        code = f":HTTP_{exc.code}" if isinstance(exc, HTTPError) else ""
        raise BundleVerificationError("CORE_LINEAGE_BUNDLE_ARTIFACT_DOWNLOAD_FAILED" + code) from exc
    return parse_json(raw) if json_response else raw


def _require_reference_index(payload: dict[str, Any]) -> dict[str, str]:
    fields = set(payload)
    require(fields in (REFERENCE_FIELDS, REFERENCE_LEGACY_FIELDS), "PAYLOAD_FIELDS_INVALID")
    require(payload.get("lineage_transport") == LINEAGE_REFERENCE_TRANSPORT, "TRANSPORT_UNSUPPORTED")
    require(payload.get("artifact_repository") == CORE_REPOSITORY, "ARTIFACT_REPOSITORY_MISMATCH")
    for field in ("artifact_run_id", "artifact_run_attempt", "artifact_id"):
        require(type(payload.get(field)) is int and payload[field] > 0, "ARTIFACT_IDENTITY_INVALID:" + field)
    require(re.fullmatch(r"publication-lineage-[1-9][0-9]*-[1-9][0-9]*-[1-9][0-9]*",
                         str(payload.get("artifact_name") or "")) is not None,
            "ARTIFACT_NAME_INVALID")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", str(payload.get("artifact_digest") or "")) is not None,
            "ARTIFACT_DIGEST_INVALID")
    if fields == REFERENCE_FIELDS:
        hashes = payload.get("content_hashes")
        require(isinstance(hashes, dict) and set(hashes) == REFERENCE_HASH_FIELDS,
                "CONTENT_HASH_FIELDS_INVALID")
    else:
        hashes = {
            "attestation": payload.get("attestation_sha256"),
            "receipt": payload.get("receipt_sha256"),
            "sigstore_bundle": payload.get("sigstore_bundle_sha256"),
        }
    for field in REFERENCE_HASH_FIELDS:
        require(re.fullmatch(r"[0-9a-f]{64}", str(hashes.get(field) or "")) is not None,
                "CONTENT_HASH_INVALID:" + field)
    return hashes


def download_reference(*, payload: dict[str, Any], output_dir: Path, token: str) -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    """Download one exact private Core artifact without requiring its run to be terminal."""
    content_hashes = _require_reference_index(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    api = "https://api.github.com/repos/" + CORE_REPOSITORY
    artifact = _request(api + "/actions/artifacts/" + str(payload["artifact_id"]), token, json_response=True)
    require(isinstance(artifact, dict), "ARTIFACT_METADATA_INVALID")
    (output_dir / "artifact-metadata.json").write_text(json.dumps(artifact, sort_keys=True) + "\n", encoding="utf-8")
    require(artifact.get("id") == payload["artifact_id"], "ARTIFACT_ID_MISMATCH")
    require(artifact.get("name") == payload["artifact_name"], "ARTIFACT_NAME_MISMATCH")
    require(artifact.get("expired") is False, "ARTIFACT_EXPIRED")
    require(artifact.get("digest") == payload["artifact_digest"], "ARTIFACT_DIGEST_MISMATCH")
    workflow_run = artifact.get("workflow_run")
    require(isinstance(workflow_run, dict) and workflow_run.get("id") == payload["artifact_run_id"],
            "ARTIFACT_RUN_MISMATCH")

    run = _request(api + "/actions/runs/" + str(payload["artifact_run_id"]), token, json_response=True)
    require(isinstance(run, dict), "ARTIFACT_RUN_METADATA_INVALID")
    (output_dir / "run-metadata.json").write_text(json.dumps(run, sort_keys=True) + "\n", encoding="utf-8")
    require(run.get("id") == payload["artifact_run_id"], "ARTIFACT_RUN_MISMATCH")
    require(run.get("run_attempt") == payload["artifact_run_attempt"], "ARTIFACT_ATTEMPT_MISMATCH")
    require((run.get("repository") or {}).get("full_name") == CORE_REPOSITORY, "ARTIFACT_REPOSITORY_MISMATCH")
    require(run.get("path") == FINALIZER_WORKFLOW and run.get("event") == "workflow_dispatch",
            "ARTIFACT_WORKFLOW_MISMATCH")
    require(run.get("head_branch") == "main", "ARTIFACT_REF_MISMATCH")
    # The finalizer deliberately dispatches while it is still running. Do not
    # require a conclusion here; all cryptographic and semantic gates follow.
    require(run.get("status") in {"queued", "in_progress", "completed"}, "ARTIFACT_RUN_STATUS_INVALID")

    archive = _request(api + "/actions/artifacts/" + str(payload["artifact_id"]) + "/zip",
                       token, json_response=False)
    (output_dir / "artifact.zip").write_bytes(archive)
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle_zip:
            names = {name for name in bundle_zip.namelist() if not name.endswith("/")}
            require(names == set(PROOF_FILES.values()), "ARTIFACT_FILES_INVALID")
            attestation = bundle_zip.read(PROOF_FILES["attestation"])
            receipt = bundle_zip.read(PROOF_FILES["receipt"])
            bundle = bundle_zip.read(PROOF_FILES["bundle"])
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise BundleVerificationError("CORE_LINEAGE_BUNDLE_ARTIFACT_ARCHIVE_INVALID") from exc
    require(_sha256(attestation) == content_hashes["attestation"], "CONTENT_HASH_MISMATCH:attestation")
    require(_sha256(receipt) == content_hashes["receipt"], "CONTENT_HASH_MISMATCH:receipt")
    require(_sha256(bundle) == content_hashes["sigstore_bundle"], "CONTENT_HASH_MISMATCH:bundle")
    return attestation, receipt, bundle, run


def verify_certificate_policy(result: Any, lineage: dict[str, Any]) -> None:
    """Only consume gh's successfully verified certificate, never the predicate."""
    require(isinstance(result, list) and len(result) == 1, "VERIFIER_RESULT_AMBIGUOUS")
    item = result[0]
    require(isinstance(item, dict), "VERIFIER_RESULT_INVALID")
    verified = item.get("verificationResult")
    require(isinstance(verified, dict), "VERIFIER_RESULT_INVALID")
    signature = verified.get("signature")
    require(isinstance(signature, dict), "VERIFIER_CERTIFICATE_MISSING")
    certificate = signature.get("certificate")
    require(isinstance(certificate, dict), "VERIFIER_CERTIFICATE_MISSING")
    timestamps = verified.get("verifiedTimestamps")
    require(isinstance(timestamps, list) and bool(timestamps), "VERIFIED_TIMESTAMP_MISSING")
    expected = {
        "issuer": OIDC_ISSUER,
        "subjectAlternativeName": SIGNER_IDENTITY,
        "sourceRepositoryURI": CORE_URI,
        "sourceRepositoryDigest": lineage["core_sha"],
        "sourceRepositoryRef": "refs/heads/main",
        "sourceRepositoryVisibilityAtSigning": "private",
        "buildSignerURI": SIGNER_IDENTITY,
        "buildSignerDigest": lineage["core_sha"],
        "buildTrigger": "workflow_dispatch",
        "runInvocationURI": (CORE_URI + "/actions/runs/" + str(lineage["finalizer"]["run_id"])
                             + "/attempts/" + str(lineage["finalizer"]["run_attempt"])),
        "runnerEnvironment": "github-hosted",
    }
    for key, value in expected.items():
        require(certificate.get(key) == value, "CERTIFICATE_IDENTITY_MISMATCH:" + key)


def verify_event(*, event: dict[str, Any], expected_public_sha: str,
                 repository: Path, output_dir: Path, artifact_token: str = "") -> dict[str, str]:
    repository, output_dir = repository.resolve(), output_dir.resolve()
    require(isinstance(event, dict), "EVENT_INVALID")
    payload = event.get("client_payload")
    require(isinstance(payload, dict), "PAYLOAD_INVALID")
    # Missing means legacy. null/empty/unknown, or any partial new envelope,
    # must not downgrade to an API lookup after failing the new contract.
    transport = payload.get("lineage_transport")
    reference = transport == LINEAGE_REFERENCE_TRANSPORT
    modern = "lineage_transport" in payload
    if reference:
        _require_reference_index(payload)
    else:
        require(set(payload) == (BUNDLE_FIELDS if modern else LEGACY_FIELDS), "PAYLOAD_FIELDS_INVALID")
        if modern:
            require(transport == LINEAGE_TRANSPORT, "TRANSPORT_UNSUPPORTED")
    require(re.fullmatch(r"[0-9a-f]{40}", expected_public_sha or "") is not None, "PUBLIC_SHA_INVALID")
    require(payload.get("public_sha") == expected_public_sha, "PUBLIC_SHA_MISMATCH")
    run = None
    if reference:
        attestation, receipt, bundle, run = download_reference(
            payload=payload, output_dir=output_dir, token=artifact_token,
        )
    else:
        attestation = decode_field(payload, "attestation_base64")
        receipt = decode_field(payload, "receipt_base64")
        require(_sha256(attestation) == payload.get("attestation_sha256"), "CONTENT_HASH_MISMATCH")
    lineage = parse_json(attestation)
    require(isinstance(lineage, dict), "LINEAGE_INVALID")
    require(re.fullmatch(r"[0-9a-f]{40}", str(lineage.get("core_sha") or "")) is not None, "CORE_SHA_INVALID")
    finalizer = lineage.get("finalizer")
    require(isinstance(finalizer, dict) and set(finalizer) == {"run_id", "run_attempt"}, "FINALIZER_INVALID")
    require(all(type(finalizer[key]) is int and finalizer[key] > 0 for key in finalizer), "FINALIZER_INVALID")
    parse_json(receipt)
    bundle = bundle if reference else None
    if modern and not reference:
        bundle = decode_field(payload, "sigstore_bundle_base64")
    if modern:
        envelope = parse_json(bundle)
        require(isinstance(envelope, dict), "BUNDLE_INVALID")
        dsse = envelope.get("dsseEnvelope")
        require(isinstance(dsse, dict) and dsse.get("payloadType") == "application/vnd.in-toto+json",
                "DSSE_PAYLOAD_TYPE_INVALID")
    output_dir.mkdir(parents=True, exist_ok=True)
    attestation_path = output_dir / "attestation.json"
    receipt_path = output_dir / "receipt.json"
    attestation_path.write_bytes(attestation)
    receipt_path.write_bytes(receipt)
    command = ["gh", "attestation", "verify", str(attestation_path), "--repo", CORE_REPOSITORY]
    if modern:
        bundle_path = output_dir / "bundle.json"
        bundle_path.write_bytes(bundle)
        command += ["--bundle", str(bundle_path), "--cert-identity", SIGNER_IDENTITY,
                    "--cert-oidc-issuer", OIDC_ISSUER, "--signer-digest", lineage["core_sha"],
                    "--deny-self-hosted-runners", "--no-public-good", "--format", "json"]
    else:
        command += ["--signer-workflow", CORE_REPOSITORY + "/" + CANONICAL_WRITER]
    command += ["--source-digest", lineage["core_sha"], "--source-ref", "refs/heads/main"]
    try:
        result = subprocess.run(command, cwd=repository, capture_output=True, check=False)
    except OSError as exc:
        raise BundleVerificationError("CORE_LINEAGE_BUNDLE_VERIFIER_UNAVAILABLE") from exc
    require(result.returncode == 0, "CRYPTOGRAPHIC_VERIFICATION_FAILED")
    if modern:
        verify_certificate_policy(parse_json(result.stdout), lineage)
    if reference:
        require(run.get("head_sha") == lineage["core_sha"], "ARTIFACT_CORE_SHA_MISMATCH")
        require(payload["artifact_run_id"] == lineage["finalizer"]["run_id"], "ARTIFACT_FINALIZER_RUN_MISMATCH")
        require(payload["artifact_run_attempt"] == lineage["finalizer"]["run_attempt"],
                "ARTIFACT_FINALIZER_ATTEMPT_MISMATCH")
        expected_name = ("publication-lineage-" + str(lineage["publisher"]["run_id"]) + "-"
                         + str(lineage["finalizer"]["run_id"]) + "-"
                         + str(lineage["finalizer"]["run_attempt"]))
        require(payload["artifact_name"] == expected_name, "ARTIFACT_NAME_LINEAGE_MISMATCH")
    # A signed but semantically crossed receipt, public SHA or bundle is invalid.
    validate_core_lineage(attestation_bytes=attestation, receipt_bytes=receipt,
                          repository=repository, expected_public_sha=expected_public_sha)
    if modern:
        (output_dir / "verification.json").write_bytes(result.stdout)
    return {"transport": transport if modern else "legacy-github-attestation-api",
            "public_sha": expected_public_sha, "core_sha": lineage["core_sha"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--expected-public-sha", required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--artifact-token-env", default="CORE_ARTIFACT_TOKEN")
    args = parser.parse_args()
    try:
        result = verify_event(event=parse_json(args.event.read_bytes()),
                              expected_public_sha=args.expected_public_sha,
                              repository=args.repository, output_dir=args.output_dir,
                              artifact_token=os.environ.get(args.artifact_token_env, ""))
    except (BundleVerificationError, CoreLineageError, OSError, ValueError, subprocess.SubprocessError) as exc:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "transport-result.json").write_text(
            json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True) + "\n", encoding="utf-8",
        )
        print("CORE_LINEAGE_AUTHENTICATION_BLOCKED " + str(exc))
        return 2
    (args.output_dir / "transport-result.json").write_text(
        json.dumps({"status": "verified", **result}, sort_keys=True) + "\n", encoding="utf-8",
    )
    print("CORE_LINEAGE_AUTHENTICATED " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
