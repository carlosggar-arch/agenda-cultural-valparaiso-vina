from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CLOUDFLARE_SYNC = WORKFLOWS / "publish.yml"
CLOUDFLARE_BUILD = ROOT / "cloudflare-build.sh"
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
    if not CLOUDFLARE_BUILD.is_file():
        raise SystemExit("CANONICAL_MAIN_BOUNDARY_MISSING_CLOUDFLARE_BUILD")
    if not CERTIFICATION_WATCHDOG.is_file():
        raise SystemExit("PRODUCTION_CERTIFICATION_WATCHDOG_MISSING")

    build = CLOUDFLARE_BUILD.read_text(encoding="utf-8")
    required_build = (
        'OUT="_cloudflare_site"',
        "find . -mindepth 1 -maxdepth 1",
        "! -name '.git'",
        "! -name '.github'",
        "! -name 'cloudflare-build.sh'",
        'test -f "$OUT/index.html"',
        'test -f "$OUT/app/index.html"',
        'test -f "$OUT/agenda_web.json"',
        'test -f "$OUT/app/data/gijon/agenda_web.json"',
        "CLOUDFLARE_PREVIEW_BUILD_OK surfaces=web,app",
    )
    missing_build = [marker for marker in required_build if marker not in build]
    if missing_build:
        raise SystemExit("CANONICAL_CLOUDFLARE_BUILD_CONTRACT_MISSING=" + repr(missing_build))

    main_writers: list[str] = []
    cloudflare_writers: list[str] = []
    certification_writers: list[str] = []
    destructive_cloudflare_writers: list[str] = []
    destructive_certification_writers: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if _pushes_branch(text, "main"):
            main_writers.append(path.name)
        if _pushes_branch(text, "cloudflare-preview"):
            cloudflare_writers.append(path.name)
        if _destructive_pushes_branch(text, "cloudflare-preview"):
            destructive_cloudflare_writers.append(path.name)
        if _pushes_branch(text, CERTIFICATION_STATE_BRANCH):
            certification_writers.append(path.name)
        if _destructive_pushes_branch(text, CERTIFICATION_STATE_BRANCH):
            destructive_certification_writers.append(path.name)

    if main_writers:
        raise SystemExit("PUBLIC_REPO_INTERNAL_MAIN_WRITERS=" + ",".join(main_writers))
    if cloudflare_writers != ["publish.yml"]:
        raise SystemExit("PUBLIC_REPO_CLOUDFLARE_WRITERS_INVALID=" + ",".join(cloudflare_writers))
    if destructive_cloudflare_writers:
        raise SystemExit("PUBLIC_REPO_CLOUDFLARE_DESTRUCTIVE_WRITERS=" + ",".join(destructive_cloudflare_writers))
    if certification_writers != ["publish.yml"]:
        raise SystemExit("PRODUCTION_CERTIFICATION_WRITERS_INVALID=" + ",".join(certification_writers))
    if destructive_certification_writers:
        raise SystemExit("PRODUCTION_CERTIFICATION_DESTRUCTIVE_WRITERS=" + ",".join(destructive_certification_writers))

    sync = CLOUDFLARE_SYNC.read_text(encoding="utf-8")
    required_sync = (
        "branches: [main]",
        '- "cloudflare-build.sh"',
        "CANDIDATE_SHA: ${{ github.sha }}",
        "ref: cloudflare-preview",
        "git fetch origin cloudflare-preview main",
        'git checkout --detach "$CANDIDATE_SHA"',
        'git merge --no-edit -s ours origin/cloudflare-preview',
        "git push origin HEAD:cloudflare-preview",
        "Require exact deployment-branch parity with candidate",
        'unexpected="$(git diff --name-only "$CANDIDATE_SHA" HEAD)"',
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
        'git merge --no-edit "$CANDIDATE_SHA"',
    ):
        if stale_dynamic_candidate in sync:
            raise SystemExit("PUBLICATION_MUTABLE_OR_CONFLICT_PRONE_HANDOFF_FORBIDDEN=" + stale_dynamic_candidate)

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
        "--force origin HEAD:cloudflare-preview",
        "--force-with-lease origin HEAD:cloudflare-preview",
        "--delete origin cloudflare-preview",
        "origin :cloudflare-preview",
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
        "candidate_sha=immutable cloudflare_handoff=exact-tree-fast-forward "
        "destructive_cloudflare_writers=0 production_certification_writer=publish.yml "
        "destructive_state_writers=0 certification_watchdog=read-only"
    )


if __name__ == "__main__":
    verify()
