from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "app" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_runtime_contracts as runtime_contracts  # noqa: E402
import release_bundle  # noqa: E402

RELEASE_PATH = ROOT / "app" / "release-version.js"
INDEX_PATH = ROOT / "app" / "index.html"
PROVENANCE_PATH = ROOT / "app" / "data" / "release-provenance.json"
RELEASE_RE = re.compile(r"const\s+RELEASE\s*=\s*(\d+)\s*;")
FINALIZER_MARKER = "[release-finalized]"
PROVENANCE_SCHEMA = "1.0.0"

GENERATED_RELEASE_FILES = frozenset({
    "app/release-version.js",
    "app/service-worker-assets.generated.js",
    "app/venue-registry.generated.mjs",
    "app/data/release-bundle.json",
    "app/data/release-provenance.json",
})
FINALIZER_ALLOWED_FILES = GENERATED_RELEASE_FILES | {"app/index.html"}
GENERATED_RELEASE_FRAGMENTS = ("app/index.html::module-release-query-keys",)
INDEX_RELEASE_PATTERNS = (
    re.compile(r'(<script\s+type="module"\s+src="\./app\.js\?v=)\d+("\s*></script>)'),
    re.compile(r'(<script\s+type="module"\s+src="\./map-navigation-enhancer\.js\?v=)\d+("\s*></script>)'),
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def git_check(*args: str) -> bool:
    return subprocess.call(["git", *args], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def git_diff_names(start: str, end: str) -> set[str]:
    return {line.strip() for line in git("diff", "--name-only", start, end).splitlines() if line.strip()}


def release_number_from_text(text: str) -> int:
    match = RELEASE_RE.search(text)
    if not match:
        raise ValueError("release-version.js must define a numeric RELEASE")
    return int(match.group(1))


def release_number_at(ref: str) -> int:
    return release_number_from_text(git("show", f"{ref}:app/release-version.js"))


def render_release_version(release: int, source_sha: str) -> str:
    return (
        "(() => {\n"
        "  // Single source of truth for the public PWA release and service-worker cache.\n"
        f"  // v{release} generated canonically from source {source_sha[:12]}.\n"
        f"  const RELEASE = {release};\n"
        "  globalThis.__VIVAMOS_RELEASE__ = RELEASE;\n"
        "})();\n"
    )


def replace_index_release_keys(text: str, release: int) -> str:
    updated = text
    for pattern in INDEX_RELEASE_PATTERNS:
        updated, count = pattern.subn(rf"\g<1>{release}\g<2>", updated)
        if count != 1:
            raise ValueError(f"app/index.html must contain exactly one canonical module release key for {pattern.pattern!r}; found {count}")
    return updated


def check_index_release_keys(release: int) -> None:
    current = INDEX_PATH.read_text(encoding="utf-8")
    if current != replace_index_release_keys(current, release):
        raise SystemExit(f"INDEX_RELEASE_KEYS_STALE expected=v{release}")


def sync_index_release_keys(release: int) -> None:
    current = INDEX_PATH.read_text(encoding="utf-8")
    INDEX_PATH.write_text(replace_index_release_keys(current, release), encoding="utf-8")


def assert_fresh(base_ref: str, head_ref: str = "HEAD") -> str:
    tip = git("rev-parse", base_ref)
    if not git_check("merge-base", "--is-ancestor", tip, head_ref):
        raise SystemExit(f"RELEASE_CANDIDATE_NOT_FRESH base={tip} head={git('rev-parse', head_ref)}")
    print(f"RELEASE_CANDIDATE_FRESH base={tip} head={git('rev-parse', head_ref)}")
    return tip


def build_provenance(*, release: int, base_sha: str, source_sha: str, source_pr: int | None) -> dict[str, object]:
    return {
        "schema_version": PROVENANCE_SCHEMA,
        "release": release,
        "base_sha": base_sha,
        "source_sha": source_sha,
        "source_pr": source_pr,
        "generator": "app/scripts/release_finalizer.py",
        "generated_artifacts": sorted(GENERATED_RELEASE_FILES),
        "generated_fragments": list(GENERATED_RELEASE_FRAGMENTS),
    }


def write_provenance(payload: dict[str, object]) -> None:
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_provenance() -> dict[str, object]:
    if not PROVENANCE_PATH.is_file():
        raise SystemExit("RELEASE_PROVENANCE_MISSING")
    payload = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != PROVENANCE_SCHEMA:
        raise SystemExit("RELEASE_PROVENANCE_SCHEMA_INVALID")
    return payload


def validate_provenance_shape(payload: dict[str, object]) -> tuple[str, str]:
    if payload.get("generator") != "app/scripts/release_finalizer.py":
        raise SystemExit("RELEASE_PROVENANCE_GENERATOR_INVALID")
    if sorted(payload.get("generated_artifacts") or []) != sorted(GENERATED_RELEASE_FILES):
        raise SystemExit("RELEASE_PROVENANCE_GENERATED_SET_INVALID")
    if list(payload.get("generated_fragments") or []) != list(GENERATED_RELEASE_FRAGMENTS):
        raise SystemExit("RELEASE_PROVENANCE_FRAGMENT_SET_INVALID")
    base_sha = str(payload.get("base_sha") or "")
    source_sha = str(payload.get("source_sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        raise SystemExit("RELEASE_PROVENANCE_BASE_INVALID")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise SystemExit("RELEASE_PROVENANCE_SOURCE_INVALID")
    return base_sha, source_sha


def validate_release_math(payload: dict[str, object], base_sha: str) -> int:
    current_release = release_number_from_text(RELEASE_PATH.read_text(encoding="utf-8"))
    expected_release = release_number_at(base_sha) + 1
    if current_release != expected_release:
        raise SystemExit(f"RELEASE_NUMBER_NOT_CANONICAL base=v{expected_release - 1} expected=v{expected_release} current=v{current_release}")
    if int(payload.get("release") or -1) != current_release:
        raise SystemExit("RELEASE_PROVENANCE_RELEASE_MISMATCH")
    check_index_release_keys(current_release)
    return current_release


def finalizer_parent(finalizer_ref: str) -> str:
    try:
        return git("rev-parse", f"{finalizer_ref}^1")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"RELEASE_FINALIZER_PARENT_MISSING ref={finalizer_ref}") from exc


def validate_generated_change_sets(change_sets: list[set[str]]) -> set[str]:
    combined: set[str] = set()
    for changes in change_sets:
        unexpected = sorted(changes - FINALIZER_ALLOWED_FILES)
        if unexpected:
            raise SystemExit("FINALIZER_CHANGED_SOURCE_FILES paths=" + ",".join(unexpected))
        combined.update(changes)
    required = {"app/release-version.js", "app/data/release-provenance.json", "app/data/release-bundle.json", "app/index.html"}
    missing = sorted(required - combined)
    if missing:
        raise SystemExit("FINALIZER_DID_NOT_OWN_REQUIRED_OUTPUTS paths=" + ",".join(missing))
    return combined


def finalizer_sequence(source_sha: str, finalizer_ref: str) -> tuple[str, list[str], list[set[str]]]:
    finalizer_sha = git("rev-parse", finalizer_ref)
    if not git_check("merge-base", "--is-ancestor", source_sha, finalizer_sha):
        raise SystemExit(f"RELEASE_FINALIZER_SOURCE_NOT_ANCESTOR source={source_sha} finalizer={finalizer_sha}")
    commits = [row.strip() for row in git("rev-list", "--reverse", "--ancestry-path", f"{source_sha}..{finalizer_sha}").splitlines() if row.strip()]
    if not commits or commits[-1] != finalizer_sha:
        raise SystemExit(f"RELEASE_FINALIZER_SEQUENCE_MISSING source={source_sha} finalizer={finalizer_sha}")
    previous = source_sha
    change_sets: list[set[str]] = []
    for commit in commits:
        parent = finalizer_parent(commit)
        if parent != previous:
            raise SystemExit(f"RELEASE_FINALIZER_SEQUENCE_NONLINEAR commit={commit} expected_parent={previous} actual_parent={parent}")
        change_sets.append(git_diff_names(previous, commit))
        previous = commit
    return finalizer_sha, commits, change_sets


def assert_finalizer_boundary(*, base_sha: str, source_sha: str, finalizer_ref: str) -> str:
    finalizer_sha = git("rev-parse", finalizer_ref)
    subject = git("log", "-1", "--format=%s", finalizer_ref)
    if FINALIZER_MARKER not in subject:
        raise SystemExit(f"RELEASE_FINALIZER_COMMIT_REQUIRED marker={FINALIZER_MARKER} subject={subject!r}")
    if not git_check("merge-base", "--is-ancestor", base_sha, source_sha):
        raise SystemExit("RELEASE_SOURCE_NOT_BASED_ON_MAIN")
    leaked = sorted(git_diff_names(base_sha, source_sha) & GENERATED_RELEASE_FILES)
    if leaked:
        raise SystemExit("GENERATED_RELEASE_FILES_CHANGED_BEFORE_FINALIZER paths=" + ",".join(leaked))
    _finalizer_sha, commits, change_sets = finalizer_sequence(source_sha, finalizer_ref)
    combined = validate_generated_change_sets(change_sets)
    print(
        f"RELEASE_FINALIZER_BOUNDARY_OK source={source_sha} finalizer={finalizer_sha} "
        f"commits={len(commits)} generated={len(combined)}"
    )
    return finalizer_sha


def deterministic_checks() -> dict:
    runtime_contracts.check_contracts()
    return release_bundle.check_release_bundle()


def prepare_release(*, base_ref: str, source_sha: str | None, source_pr: int | None) -> dict[str, object]:
    base_sha = assert_fresh(base_ref)
    source = source_sha or git("rev-parse", "HEAD")
    if source != git("rev-parse", "HEAD"):
        raise SystemExit("RELEASE_PREPARE_REQUIRES_SOURCE_AT_HEAD")
    if not git_check("merge-base", "--is-ancestor", base_sha, source):
        raise SystemExit(f"RELEASE_SOURCE_NOT_FRESH source={source} base={base_sha}")
    next_release = release_number_at(base_sha) + 1
    RELEASE_PATH.write_text(render_release_version(next_release, source), encoding="utf-8")
    sync_index_release_keys(next_release)
    write_provenance(build_provenance(release=next_release, base_sha=base_sha, source_sha=source, source_pr=source_pr))
    runtime_contracts.write_contracts()
    release_bundle.write_release_bundle()
    deterministic_checks()
    print(f"RELEASE_CANDIDATE_PREPARED release=v{next_release} base={base_sha} source={source} pr={source_pr or 'n/a'}")
    return load_provenance()


def check_candidate(*, base_ref: str, finalizer_ref: str) -> dict[str, object]:
    current_base = assert_fresh(base_ref, finalizer_ref)
    payload = load_provenance()
    base_sha, source_sha = validate_provenance_shape(payload)
    if base_sha != current_base:
        raise SystemExit(f"RELEASE_PROVENANCE_BASE_STALE expected={current_base} actual={base_sha}")
    finalizer_sha = assert_finalizer_boundary(base_sha=base_sha, source_sha=source_sha, finalizer_ref=finalizer_ref)
    current_release = validate_release_math(payload, base_sha)
    bundle = deterministic_checks()
    print(f"RELEASE_FINALIZATION_OK release=v{current_release} base={base_sha} source={source_sha} finalizer={finalizer_sha} pr={payload.get('source_pr') or 'n/a'} release_id={bundle['release_id']}")
    return payload


def find_published_finalizer(source_sha: str, head_ref: str = "HEAD") -> str:
    for row in git("log", "--format=%H%x00%s", "--ancestry-path", f"{source_sha}..{head_ref}").splitlines():
        sha, _, subject = row.partition("\x00")
        if FINALIZER_MARKER in subject and git_check("merge-base", "--is-ancestor", source_sha, sha):
            return sha
    raise SystemExit(f"PUBLISHED_FINALIZER_NOT_FOUND source={source_sha} head={git('rev-parse', head_ref)}")


def check_published(head_ref: str = "HEAD") -> dict[str, object]:
    payload = load_provenance()
    base_sha, source_sha = validate_provenance_shape(payload)
    head_sha = git("rev-parse", head_ref)
    for label, sha in (("base", base_sha), ("source", source_sha)):
        if not git_check("merge-base", "--is-ancestor", sha, head_sha):
            raise SystemExit(f"PUBLISHED_{label.upper()}_NOT_ANCESTOR sha={sha} head={head_sha}")
    finalizer_sha = find_published_finalizer(source_sha, head_ref)
    assert_finalizer_boundary(base_sha=base_sha, source_sha=source_sha, finalizer_ref=finalizer_sha)
    if not git_check("merge-base", "--is-ancestor", finalizer_sha, head_sha):
        raise SystemExit("PUBLISHED_FINALIZER_NOT_ANCESTOR")
    current_release = validate_release_math(payload, base_sha)
    bundle = deterministic_checks()
    print(f"PUBLISHED_RELEASE_CHAIN_OK pr={payload.get('source_pr') or 'n/a'} base={base_sha} source={source_sha} finalizer={finalizer_sha} main={head_sha} release=v{current_release} release_id={bundle['release_id']}")
    return {**payload, "finalizer_sha": finalizer_sha, "main_sha": head_sha, "release_id": bundle["release_id"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Canonical release finalizer: fresh-main gate, automatic release number, generated-output ownership and provenance.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--check", action="store_true")
    action.add_argument("--fresh", action="store_true")
    action.add_argument("--check-published", action="store_true")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--source-sha", default=None)
    parser.add_argument("--source-pr", type=int, default=None)
    parser.add_argument("--finalizer-ref", default="HEAD")
    args = parser.parse_args()
    if args.fresh:
        assert_fresh(args.base_ref, args.finalizer_ref)
    elif args.prepare:
        prepare_release(base_ref=args.base_ref, source_sha=args.source_sha, source_pr=args.source_pr)
    elif args.check:
        check_candidate(base_ref=args.base_ref, finalizer_ref=args.finalizer_ref)
    else:
        check_published(args.finalizer_ref)


if __name__ == "__main__":
    main()
