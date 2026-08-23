from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "app/service-worker-assets.generated.js"
RELEASE = "app/release-version.js"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def manifest_assets(source: str) -> set[str]:
    match = re.search(r"__VIVAMOS_SHELL_ASSETS__\s*=\s*Object\.freeze\((\[[\s\S]*?\])\)", source)
    if not match:
        raise AssertionError("generated shell manifest payload not found")
    paths: set[str] = set()
    for value in json.loads(match.group(1)):
        clean = value.split("?", 1)[0]
        if clean == "./":
            clean = "./index.html"
        normalized = PurePosixPath("app", clean).as_posix()
        paths.add(normalized)
    return paths


def release_number(source: str) -> int:
    match = re.search(r"const\s+RELEASE\s*=\s*(\d+)\s*;", source)
    if not match:
        raise AssertionError("release-version.js must define RELEASE")
    return int(match.group(1))


def main() -> None:
    base_branch = os.environ.get("GITHUB_BASE_REF", "main")
    base = git("merge-base", "HEAD", f"origin/{base_branch}")
    changed = set(filter(None, git("diff", "--name-only", f"{base}...HEAD").splitlines()))

    current_manifest = (ROOT / MANIFEST).read_text(encoding="utf-8")
    base_manifest = git("show", f"{base}:{MANIFEST}")
    runtime_paths = manifest_assets(current_manifest) | manifest_assets(base_manifest)
    changed_runtime = sorted(changed & runtime_paths)

    if not changed_runtime:
        print("RELEASE_DELTA_OK runtime_assets_changed=0")
        return

    current_release = release_number((ROOT / RELEASE).read_text(encoding="utf-8"))
    base_release = release_number(git("show", f"{base}:{RELEASE}"))
    if current_release <= base_release:
        raise SystemExit(
            "RELEASE_DELTA_REQUIRED "
            f"base=v{base_release} current=v{current_release} "
            "runtime_assets=" + ",".join(changed_runtime)
        )
    print(
        "RELEASE_DELTA_OK "
        f"base=v{base_release} current=v{current_release} "
        f"runtime_assets_changed={len(changed_runtime)}"
    )


if __name__ == "__main__":
    main()
