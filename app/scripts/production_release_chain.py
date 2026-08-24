from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from release_finalizer import check_published, git, git_check

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


def build_chain(*, cloudflare_ref: str, attestation_path: Path) -> dict[str, object]:
    published = check_published("HEAD")
    main_sha = str(published["main_sha"])
    try:
        cloudflare_sha = git("rev-parse", cloudflare_ref)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"RELEASE_CHAIN_CLOUDFLARE_REF_MISSING ref={cloudflare_ref}") from exc
    if not git_check("merge-base", "--is-ancestor", main_sha, cloudflare_sha):
        raise SystemExit(f"RELEASE_CHAIN_CLOUDFLARE_STALE main={main_sha} cloudflare={cloudflare_sha}")
    attestation = load_json(attestation_path)
    validate_visual_attestation(attestation, published)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_pr": published.get("source_pr"),
        "base_sha": published["base_sha"],
        "source_sha": published["source_sha"],
        "finalizer_sha": published["finalizer_sha"],
        "main_sha": main_sha,
        "cloudflare_sha": cloudflare_sha,
        "release": published["release"],
        "release_id": published["release_id"],
        "production_attestation_head": attestation["head_sha"],
        "publication_state": "source_to_production_certified",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Certify source PR -> finalizer -> main -> Cloudflare -> production.")
    parser.add_argument("--cloudflare-ref", default="origin/cloudflare-preview")
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = build_chain(cloudflare_ref=args.cloudflare_ref, attestation_path=Path(args.attestation))
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
