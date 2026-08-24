from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CLOUDFLARE_SYNC = WORKFLOWS / "publish.yml"
CERTIFICATION_STATE_BRANCH = "state/production-certifications"


def _pushes_branch(text: str, branch: str) -> bool:
    # Accept the canonical `git push ...` form and scoped working-directory
    # commands such as `git -C <path> push ...`; both are branch writers.
    git_push = r"git(?:\s+-C\s+\S+)?\s+push"
    patterns = (
        rf"{git_push}\s+[^\n]*HEAD:{re.escape(branch)}\b",
        rf"{git_push}\s+[^\n]*refs/heads/{re.escape(branch)}\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _destructive_pushes_branch(text: str, branch: str) -> bool:
    git_push = r"git(?:\s+-C\s+\S+)?\s+push"
    force = rf"{git_push}\s+[^\n]*(?:--force(?:-with-lease)?|\s-f\b)[^\n]*(?:{re.escape(branch)}|refs/heads/{re.escape(branch)})"
    delete_refspec = rf"{git_push}\s+[^\n]*(?::(?:refs/heads/)?{re.escape(branch)}\b|--delete\s+\S+\s+{re.escape(branch)}\b)"
    return bool(re.search(force, text) or re.search(delete_refspec, text))


def verify() -> None:
    if not CLOUDFLARE_SYNC.is_file():
        raise SystemExit("CANONICAL_MAIN_BOUNDARY_MISSING_CLOUDFLARE_SYNC")

    main_writers: list[str] = []
    cloudflare_writers: list[str] = []
    certification_writers: list[str] = []
    destructive_certification_writers: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if _pushes_branch(text, "main"):
            main_writers.append(path.name)
        if _pushes_branch(text, "cloudflare-preview"):
            cloudflare_writers.append(path.name)
        if _pushes_branch(text, CERTIFICATION_STATE_BRANCH):
            certification_writers.append(path.name)
        if _destructive_pushes_branch(text, CERTIFICATION_STATE_BRANCH):
            destructive_certification_writers.append(path.name)

    if main_writers:
        raise SystemExit("PUBLIC_REPO_INTERNAL_MAIN_WRITERS=" + ",".join(main_writers))
    if cloudflare_writers != ["publish.yml"]:
        raise SystemExit(
            "PUBLIC_REPO_CLOUDFLARE_WRITERS_INVALID=" + ",".join(cloudflare_writers)
        )
    if certification_writers != ["publish.yml"]:
        raise SystemExit(
            "PRODUCTION_CERTIFICATION_WRITERS_INVALID=" + ",".join(certification_writers)
        )
    if destructive_certification_writers:
        raise SystemExit(
            "PRODUCTION_CERTIFICATION_DESTRUCTIVE_WRITERS=" + ",".join(destructive_certification_writers)
        )

    sync = CLOUDFLARE_SYNC.read_text(encoding="utf-8")
    required = (
        "branches: [main]",
        "ref: cloudflare-preview",
        "git fetch origin main",
        "git merge --no-edit origin/main",
        "git push origin HEAD:cloudflare-preview",
        "Guard Cloudflare-only divergence",
        "grep -v '^cloudflare-build\\.sh$'",
        f"ref: {CERTIFICATION_STATE_BRANCH}",
        f"git -C .production-certification-state push origin HEAD:{CERTIFICATION_STATE_BRANCH}",
        "production_certification_history.py",
        "production_certification_watchdog.py",
        "PRODUCTION_UNCERTIFIED",
        "certification-watchdog:",
    )
    missing = [marker for marker in required if marker not in sync]
    if missing:
        raise SystemExit("PUBLICATION_WRITER_CONTRACT_MISSING=" + repr(missing))

    for forbidden in (
        "git push origin HEAD:main",
        "git push origin main",
        f"--force origin HEAD:{CERTIFICATION_STATE_BRANCH}",
        f"--force-with-lease origin HEAD:{CERTIFICATION_STATE_BRANCH}",
        f"--delete origin {CERTIFICATION_STATE_BRANCH}",
        f"origin :{CERTIFICATION_STATE_BRANCH}",
    ):
        if forbidden in sync:
            raise SystemExit("PUBLICATION_DESTRUCTIVE_WRITE_FORBIDDEN=" + forbidden)

    # Canonical datasets remain writable only by the external core finalizer.
    # The public repository owns two explicit stateful deployment outputs: the
    # Cloudflare mirror and append-only production certification history. The
    # latter is guarded against destructive internal writes and cryptographically
    # verified by the production watchdog after every synchronized deployment.
    print(
        "CANONICAL_PUBLICATION_WRITERS_OK "
        "main_internal_writers=0 cloudflare_mirror_writer=publish.yml "
        "production_certification_writer=publish.yml destructive_state_writers=0 "
        "certification_watchdog=required"
    )


if __name__ == "__main__":
    verify()
