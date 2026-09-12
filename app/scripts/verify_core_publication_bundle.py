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
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from core_publication_lineage import (
    CANONICAL_WRITER, CORE_REPOSITORY, CoreLineageError, validate as validate_core_lineage,
)

# The Core writer reads this literal capability from its immutable Web baseline.
LINEAGE_TRANSPORT = "github-sigstore-bundle-v1"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
CORE_URI = "https://github.com/" + CORE_REPOSITORY
SIGNER_IDENTITY = CORE_URI + "/" + CANONICAL_WRITER + "@refs/heads/main"
LEGACY_FIELDS = {"public_sha", "attestation_base64", "attestation_sha256", "receipt_base64"}
BUNDLE_FIELDS = LEGACY_FIELDS | {"lineage_transport", "sigstore_bundle_base64"}


class BundleVerificationError(RuntimeError):
    pass


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
                 repository: Path, output_dir: Path) -> dict[str, str]:
    repository, output_dir = repository.resolve(), output_dir.resolve()
    require(isinstance(event, dict), "EVENT_INVALID")
    payload = event.get("client_payload")
    require(isinstance(payload, dict), "PAYLOAD_INVALID")
    # Missing means legacy. null/empty/unknown, or any partial new envelope,
    # must not downgrade to an API lookup after failing the new contract.
    modern = "lineage_transport" in payload
    require(set(payload) == (BUNDLE_FIELDS if modern else LEGACY_FIELDS), "PAYLOAD_FIELDS_INVALID")
    if modern:
        require(payload["lineage_transport"] == LINEAGE_TRANSPORT, "TRANSPORT_UNSUPPORTED")
    require(re.fullmatch(r"[0-9a-f]{40}", expected_public_sha or "") is not None, "PUBLIC_SHA_INVALID")
    require(payload.get("public_sha") == expected_public_sha, "PUBLIC_SHA_MISMATCH")
    attestation = decode_field(payload, "attestation_base64")
    receipt = decode_field(payload, "receipt_base64")
    require(hashlib.sha256(attestation).hexdigest() == payload.get("attestation_sha256"), "CONTENT_HASH_MISMATCH")
    lineage = parse_json(attestation)
    require(isinstance(lineage, dict), "LINEAGE_INVALID")
    require(re.fullmatch(r"[0-9a-f]{40}", str(lineage.get("core_sha") or "")) is not None, "CORE_SHA_INVALID")
    finalizer = lineage.get("finalizer")
    require(isinstance(finalizer, dict) and set(finalizer) == {"run_id", "run_attempt"}, "FINALIZER_INVALID")
    require(all(type(finalizer[key]) is int and finalizer[key] > 0 for key in finalizer), "FINALIZER_INVALID")
    parse_json(receipt)
    bundle = None
    if modern:
        bundle = decode_field(payload, "sigstore_bundle_base64")
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
    # A signed but semantically crossed receipt, public SHA or bundle is invalid.
    validate_core_lineage(attestation_bytes=attestation, receipt_bytes=receipt,
                          repository=repository, expected_public_sha=expected_public_sha)
    if modern:
        (output_dir / "verification.json").write_bytes(result.stdout)
    return {"transport": LINEAGE_TRANSPORT if modern else "legacy-github-attestation-api",
            "public_sha": expected_public_sha, "core_sha": lineage["core_sha"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--expected-public-sha", required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify_event(event=parse_json(args.event.read_bytes()),
                              expected_public_sha=args.expected_public_sha,
                              repository=args.repository, output_dir=args.output_dir)
    except (BundleVerificationError, CoreLineageError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print("CORE_LINEAGE_AUTHENTICATION_BLOCKED " + str(exc))
        return 2
    print("CORE_LINEAGE_AUTHENTICATED " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
