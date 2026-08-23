from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CLOUDFLARE_SYNC = WORKFLOWS / "publish.yml"


def _pushes_branch(text: str, branch: str) -> bool:
    patterns = (
        rf"git\s+push\s+[^\n]*HEAD:{re.escape(branch)}\b",
        rf"git\s+push\s+[^\n]*refs/heads/{re.escape(branch)}\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def verify() -> None:
    if not CLOUDFLARE_SYNC.is_file():
        raise SystemExit("CANONICAL_MAIN_BOUNDARY_MISSING_CLOUDFLARE_SYNC")

    main_writers: list[str] = []
    cloudflare_writers: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if _pushes_branch(text, "main"):
            main_writers.append(path.name)
        if _pushes_branch(text, "cloudflare-preview"):
            cloudflare_writers.append(path.name)

    if main_writers:
        raise SystemExit("PUBLIC_REPO_INTERNAL_MAIN_WRITERS=" + ",".join(main_writers))
    if cloudflare_writers != ["publish.yml"]:
        raise SystemExit(
            "PUBLIC_REPO_CLOUDFLARE_WRITERS_INVALID=" + ",".join(cloudflare_writers)
        )

    sync = CLOUDFLARE_SYNC.read_text(encoding="utf-8")
    required = (
        "branches: [main]",
        "ref: cloudflare-preview",
        "git fetch origin main",
        "git merge --ff-only origin/main",
        "git push origin HEAD:cloudflare-preview",
        "Fast-forward deployment branch from approved main",
    )
    missing = [marker for marker in required if marker not in sync]
    if missing:
        raise SystemExit("CLOUDFLARE_MIRROR_CONTRACT_MISSING=" + repr(missing))

    for forbidden in (
        "git push origin HEAD:main",
        "git push origin main",
    ):
        if forbidden in sync:
            raise SystemExit("CLOUDFLARE_SYNC_WRITES_CANONICAL_MAIN")

    # Canonical datasets are intentionally writable only by the external core
    # finalizer. Workflows in this repository may validate them and the mirror
    # workflow may deploy them, but no internal workflow may commit them to main.
    print(
        "CANONICAL_MAIN_EXTERNAL_WRITER_OK "
        "main_internal_writers=0 cloudflare_mirror_writer=publish.yml"
    )


if __name__ == "__main__":
    verify()
