from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "app/data/release-bundle.json"
RELEASE_PATH = ROOT / "app/release-version.js"

COMPONENTS = {
    "dataset_valparaiso": ROOT / "agenda_web.json",
    "dataset_gijon": ROOT / "app/data/gijon/agenda_web.json",
    "source_catalog": ROOT / "fuentes_publicas.json",
    "source_registry": ROOT / "app/data/source-registry.json",
    "diagnostic_source_coverage": ROOT / "app/data/quality/source-coverage.json",
    "diagnostic_event_quality": ROOT / "app/data/quality/event-quality.json",
    "diagnostic_release_readiness": ROOT / "app/data/quality/release-readiness.json",
    "venue_registry": ROOT / "app/data/venue-registry.json",
    "service_worker_manifest": ROOT / "app/service-worker-assets.generated.js",
    "release_version": RELEASE_PATH,
    "release_provenance": ROOT / "app/data/release-provenance.json",
    "index_shell": ROOT / "app/index.html",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def release_number() -> int:
    match = re.search(r"const\s+RELEASE\s*=\s*(\d+)\s*;", RELEASE_PATH.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("RELEASE constant not found")
    return int(match.group(1))


def build_release_bundle() -> dict:
    missing = [str(path.relative_to(ROOT)) for path in COMPONENTS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing release components: " + ", ".join(missing))
    components = {
        name: {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha": git_blob_sha(path)}
        for name, path in COMPONENTS.items()
    }
    digest_input = json.dumps({name: row["sha"] for name, row in components.items()}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint = hashlib.sha256(digest_input).hexdigest()
    release = release_number()
    return {
        "schema_version": "1.0.0",
        "release": release,
        "release_id": f"v{release}-{fingerprint[:12]}",
        "fingerprint": fingerprint,
        "hash_algorithm": "git_blob_sha1",
        "components": components,
    }


def write_release_bundle() -> dict:
    bundle = build_release_bundle()
    BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUNDLE_PATH.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bundle


def check_release_bundle() -> dict:
    expected = build_release_bundle()
    if not BUNDLE_PATH.exists():
        raise SystemExit("RELEASE_BUNDLE_MISSING")
    current = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if current != expected:
        changed = []
        current_components = current.get("components") or {}
        for name, row in expected["components"].items():
            if (current_components.get(name) or {}).get("sha") != row["sha"]:
                changed.append(name)
        if current.get("release") != expected["release"]:
            changed.append("release")
        raise SystemExit("RELEASE_BUNDLE_STALE components=" + ",".join(changed or ["fingerprint"]))
    print(f"RELEASE_BUNDLE_OK release_id={expected['release_id']}")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description="Create/check the deterministic Vivamos release generation bundle.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        bundle = write_release_bundle()
        print(f"RELEASE_BUNDLE_WRITTEN release_id={bundle['release_id']}")
    else:
        check_release_bundle()


if __name__ == "__main__":
    main()
