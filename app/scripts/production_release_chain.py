from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from release_finalizer import check_published, git, git_check
import publication_snapshot_verification as snapshot_contract

SCHEMA_VERSION = "1.0.0"


def load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise SystemExit(f"Missing release-chain evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_visual_attestation(attestation: dict[str, object], published: dict[str, object]) -> None:
    if int(attestation.get("release") or -1) != int(published.get("release") or -1):
        raise SystemExit("RELEASE_CHAIN_ATTESTATION_RELEASE_MISMATCH")
    if str(attestation.get("release_id") or "") != str(published.get("release_id") or ""):
        raise SystemExit("RELEASE_CHAIN_ATTESTATION_ID_MISMATCH")
    if str(attestation.get("head_sha") or "") != str(published.get("main_sha") or ""):
        raise SystemExit("RELEASE_CHAIN_ATTESTATION_HEAD_MISMATCH")
    if attestation.get("publication_state") != "published_and_visually_verified":
        raise SystemExit("RELEASE_CHAIN_VISUAL_ATTESTATION_INCOMPLETE")


def validate_cloudflare_relation(main_sha: str, cloudflare_sha: str, *, snapshot_mode: bool) -> tuple[str, list[str]]:
    if git_check("merge-base", "--is-ancestor", main_sha, cloudflare_sha):
        return "ancestor", []
    if not snapshot_mode:
        raise SystemExit(f"RELEASE_CHAIN_CLOUDFLARE_STALE main={main_sha} cloudflare={cloudflare_sha}")
    changed = sorted(set(filter(None, git("diff", "--name-only", main_sha, cloudflare_sha).splitlines())))
    if not changed or not all(snapshot_contract.non_public_verification_path(path) for path in changed):
        raise SystemExit(f"RELEASE_CHAIN_CLOUDFLARE_SURFACES_CHANGED main={main_sha} cloudflare={cloudflare_sha}")
    return "verified-non-public-diff", changed


def validate_runtime_release(runtime_sha: str) -> tuple[dict[str, object], str, list[str]]:
    release_owner = git("log", "-1", "--format=%H", runtime_sha, "--", "app/data/release-provenance.json")
    if len(release_owner) != 40 or not git_check("merge-base", "--is-ancestor", release_owner, runtime_sha):
        raise SystemExit("SNAPSHOT_RUNTIME_RELEASE_OWNER_INVALID")
    changed = [] if release_owner == runtime_sha else sorted(set(filter(None,
        git("diff", "--name-only", release_owner, runtime_sha).splitlines())))
    if not all(snapshot_contract.non_public_verification_path(path) for path in changed):
        raise SystemExit("SNAPSHOT_RUNTIME_RELEASE_SURFACES_CHANGED")
    published = check_published(release_owner)
    if str(published["main_sha"]) != release_owner:
        raise SystemExit("SNAPSHOT_RUNTIME_RELEASE_OWNER_MISMATCH")
    return published, release_owner, changed


def build_chain(
    *, cloudflare_ref: str, attestation_path: Path,
    core_attestation: Path | None = None, core_receipt: Path | None = None,
    snapshot_verification: Path | None = None,
    historical_validation: Path | None = None,
) -> dict[str, object]:
    # These are the original bytes authenticated earlier by the consumer. Keep
    # their semantic checks through the final chain, never fall back to PR mode.
    if (core_attestation is None) != (core_receipt is None):
        raise SystemExit("CORE_PUBLICATION_LINEAGE_EVIDENCE_INCOMPLETE")
    proof = load_json(snapshot_verification) if snapshot_verification is not None else None
    if proof is not None:
        proof = snapshot_contract.validate(proof)
        if core_attestation is None:
            raise SystemExit("SNAPSHOT_HISTORICAL_LINEAGE_EVIDENCE_REQUIRED")
        if historical_validation is None:
            raise SystemExit("SNAPSHOT_HISTORICAL_VALIDATION_REQUIRED")
        composition = proof["composition"]
        historical_bytes = historical_validation.read_bytes()
        historical = load_json(historical_validation)
        if (str(historical["main_sha"]) != composition["historical"]["head_sha"]
                or str(historical["release_id"]) != composition["historical"]["release_id"]
                or historical.get("lineage_mode") != "CORE_PUBLICATION_FINALIZER"):
            raise SystemExit("SNAPSHOT_HISTORICAL_RELEASE_IDENTITY_MISMATCH")
        # The original signed lineage authenticates the preserved data object.
        # Current runtime authority comes from the exact reviewed tree and its
        # own release contract, never by pretending the old Core claim signed it.
        runtime_sha = composition["runtime"]["head_sha"]
        published, runtime_release_owner, runtime_verification_paths = validate_runtime_release(runtime_sha)
        if str(published["release_id"]) != composition["runtime"]["release_id"]:
            raise SystemExit("SNAPSHOT_RUNTIME_RELEASE_IDENTITY_MISMATCH")
        effective_published = {**published, "main_sha": runtime_sha}
    elif core_attestation is not None:
        published = check_published("HEAD", core_attestation=core_attestation, core_receipt=core_receipt)
        effective_published = published
    else:
        if historical_validation is not None:
            raise SystemExit("UNEXPECTED_HISTORICAL_VALIDATION")
        published = check_published("HEAD")
        effective_published = published
    main_sha = str(effective_published["main_sha"])
    try:
        cloudflare_sha = git("rev-parse", cloudflare_ref)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"RELEASE_CHAIN_CLOUDFLARE_REF_MISSING ref={cloudflare_ref}") from exc
    cloudflare_relation, cloudflare_changed_paths = validate_cloudflare_relation(
        main_sha, cloudflare_sha, snapshot_mode=proof is not None)
    attestation = load_json(attestation_path)
    validate_visual_attestation(attestation, effective_published)
    result = {
        "schema_version": SCHEMA_VERSION,
        "lineage_mode": published["lineage_mode"],
        "source_pr": published.get("source_pr"),
        "base_sha": published["base_sha"],
        "source_sha": published["source_sha"],
        "finalizer_sha": published["finalizer_sha"],
        "main_sha": main_sha,
        "cloudflare_sha": cloudflare_sha,
        "cloudflare_relation": cloudflare_relation,
        "release": published["release"],
        "release_id": published["release_id"],
        "production_attestation_head": attestation["head_sha"],
        "publication_state": "source_to_production_certified",
    }
    if proof is not None:
        result.update({
            "lineage_mode": "historical-data-current-runtime-composition",
            "historical_public_sha": proof["composition"]["historical"]["head_sha"],
            "historical_release_id": proof["composition"]["historical"]["release_id"],
            "historical_success_claimed": False,
            "historical_validation_sha256": hashlib.sha256(historical_bytes).hexdigest(),
            "snapshot_verification_sha256": snapshot_contract.proof_hash(proof),
            "cloudflare_non_public_changed_paths": cloudflare_changed_paths,
            "runtime_release_owner_sha": runtime_release_owner,
            "runtime_verification_changed_paths": runtime_verification_paths,
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Certify source PR -> finalizer -> main -> Cloudflare -> production.")
    parser.add_argument("--cloudflare-ref", default="origin/cloudflare-preview")
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--core-attestation", type=Path)
    parser.add_argument("--core-receipt", type=Path)
    parser.add_argument("--snapshot-verification", type=Path)
    parser.add_argument("--historical-validation", type=Path)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    arguments = {"cloudflare_ref": args.cloudflare_ref, "attestation_path": Path(args.attestation),
                 "core_attestation": args.core_attestation, "core_receipt": args.core_receipt}
    if args.snapshot_verification is not None:
        arguments["snapshot_verification"] = args.snapshot_verification
    if args.historical_validation is not None:
        arguments["historical_validation"] = args.historical_validation
    payload = build_chain(**arguments)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PRODUCTION_RELEASE_CHAIN_CERTIFIED "
        f"pr={payload.get('source_pr') or 'n/a'} source={payload['source_sha']} finalizer={payload['finalizer_sha']} "
        f"main={payload['main_sha']} cloudflare={payload['cloudflare_sha']} release=v{payload['release']} "
        f"release_id={payload['release_id']} state={payload['publication_state']}"
    )


if __name__ == "__main__":
    main()
