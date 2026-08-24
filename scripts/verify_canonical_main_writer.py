from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CLOUDFLARE_SYNC = WORKFLOWS / "publish.yml"
CERTIFICATION_WATCHDOG = WORKFLOWS / "production-certification-watchdog.yml"
CERTIFICATION_STATE_BRANCH = "state/production-certifications"


def _pushes_branch(text: str, branch: str) -> bool:
    git_push = r"git(?:\s+-C\s+\S+)?\s+push"
    patterns = (
        rf"{git_push}\s+[^\n]*HEAD:{re.escape(branch)}\b",
        rf"{git_push}\s+[^\n]*refs/heads/{re.escape(branch)}\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _destructive_pushes_branch(text: str, branch: str) -> bool:
    """Detect only force/delete pushes to branch; normal HEAD:branch is safe."""
    git_push = re.compile(r"git(?:\s+-C\s+\S+)?\s+push\b")
    target = re.escape(branch)
    for line in text.splitlines():
        if not git_push.search(line):
            continue
        if branch not in line and f"refs/heads/{branch}" not in line:
            continue
        if re.search(r"(?:^|\s)(?:--force(?:-with-lease)?|-f)(?:\s|$)", line):
            return True
        if re.search(rf"--delete\s+\S+\s+(?:refs/heads/)?{target}(?:\s|$)", line):
            return True
        # A deletion refspec has no source ref: `:branch`. Requiring whitespace
        # before the colon prevents false positives on normal `HEAD:branch`.
        if re.search(rf"(?:^|\s):(?:refs/heads/)?{target}(?:\s|$)", line):
            return True
    return False


def verify() -> None:
    if not CLOUDFLARE_SYNC.is_file():
        raise SystemExit("CANONICAL_MAIN_BOUNDARY_MISSING_CLOUDFLARE_SYNC")
    if not CERTIFICATION_WATCHDOG.is_file():
        raise SystemExit("PRODUCTION_CERTIFICATION_WATCHDOG_MISSING")

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
        raise SystemExit("PUBLIC_REPO_CLOUDFLARE_WRITERS_INVALID=" + ",".join(cloudflare_writers))
    if certification_writers != ["publish.yml"]:
        raise SystemExit("PRODUCTION_CERTIFICATION_WRITERS_INVALID=" + ",".join(certification_writers))
    if destructive_certification_writers:
        raise SystemExit("PRODUCTION_CERTIFICATION_DESTRUCTIVE_WRITERS=" + ",".join(destructive_certification_writers))

    sync = CLOUDFLARE_SYNC.read_text(encoding="utf-8")
    required_sync = (
        "branches: [main]",
        "CANDIDATE_SHA: ${{ github.sha }}",
        "ref: cloudflare-preview",
        "git fetch origin main",
        'git merge --no-edit "$CANDIDATE_SHA"',
        "git push origin HEAD:cloudflare-preview",
        "Guard Cloudflare-only divergence from exact candidate",
        "grep -v '^cloudflare-build\\.sh$'",
        'ref: ${{ github.sha }}',
        'test "$(git rev-parse HEAD)" = "$CANDIDATE_SHA"',
        f"ref: {CERTIFICATION_STATE_BRANCH}",
        f"git -C .production-certification-state push origin HEAD:{CERTIFICATION_STATE_BRANCH}",
        "production_certification_history.py",
    )
    missing = [marker for marker in required_sync if marker not in sync]
    if missing:
        raise SystemExit("PUBLICATION_WRITER_CONTRACT_MISSING=" + repr(missing))

    for stale_dynamic_candidate in (
        "git merge --no-edit origin/main",
        "git reset --hard origin/main",
    ):
        if stale_dynamic_candidate in sync:
            raise SystemExit("PUBLICATION_MUTABLE_CANDIDATE_FORBIDDEN=" + stale_dynamic_candidate)

    watchdog = CERTIFICATION_WATCHDOG.read_text(encoding="utf-8")
    required_watchdog = (
        "workflow_run:",
        'workflows: ["Publish and production verification"]',
        "types: [completed]",
        "actions: read",
        f"ref: {CERTIFICATION_STATE_BRANCH}",
        "production_certification_watchdog.py",
        "PRODUCTION_UNCERTIFIED",
        "sync-cloudflare",
        "production-smoke",
        "production-release-attestation.json",
    )
    missing_watchdog = [marker for marker in required_watchdog if marker not in watchdog]
    if missing_watchdog:
        raise SystemExit("PRODUCTION_CERTIFICATION_WATCHDOG_CONTRACT_MISSING=" + repr(missing_watchdog))
    if "contents: write" in watchdog:
        raise SystemExit("PRODUCTION_CERTIFICATION_WATCHDOG_MUST_BE_READ_ONLY")

    for forbidden in (
        "git push origin HEAD:main",
        "git push origin main",
        f"--force origin HEAD:{CERTIFICATION_STATE_BRANCH}",
        f"--force-with-lease origin HEAD:{CERTIFICATION_STATE_BRANCH}",
        f"--delete origin {CERTIFICATION_STATE_BRANCH}",
        f"origin :{CERTIFICATION_STATE_BRANCH}",
    ):
        if forbidden in sync or forbidden in watchdog:
            raise SystemExit("PUBLICATION_DESTRUCTIVE_WRITE_FORBIDDEN=" + forbidden)

    print(
        "CANONICAL_PUBLICATION_WRITERS_OK "
        "main_internal_writers=0 cloudflare_mirror_writer=publish.yml "
        "candidate_sha=immutable production_certification_writer=publish.yml "
        "destructive_state_writers=0 certification_watchdog=read-only"
    )


if __name__ == "__main__":
    verify()
