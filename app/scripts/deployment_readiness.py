from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from production_pwa_smoke import (
    CRITICAL_ASSETS,
    ORIGINS,
    canonical_manifest_asset,
    expected_shell,
    fetch_bytes,
    fetch_text,
    local_hash,
    manifest_has,
    release_number,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_POLL_SECONDS = 2.0
FETCH_TIMEOUT_SECONDS = 5
MAX_PARALLEL_FETCHES = 8
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def candidate_release(candidate_sha: str) -> int:
    text = subprocess.check_output(
        ["git", "show", f"{candidate_sha}:app/release-version.js"], cwd=ROOT, text=True
    )
    match = re.search(r"const RELEASE = (\d+);", text)
    if not match:
        raise SystemExit(f"DEPLOYMENT_CANDIDATE_RELEASE_MISSING candidate={candidate_sha}")
    return int(match.group(1))


def validate_candidate(candidate_sha: str) -> int:
    if not SHA_RE.fullmatch(candidate_sha):
        raise SystemExit(f"DEPLOYMENT_CANDIDATE_SHA_INVALID candidate={candidate_sha!r}")
    subprocess.check_call(
        ["git", "merge-base", "--is-ancestor", candidate_sha, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    expected = candidate_release(candidate_sha)
    local = release_number()
    if local != expected:
        raise SystemExit(
            f"DEPLOYMENT_CANDIDATE_WORKTREE_MISMATCH candidate={candidate_sha} candidate_release=v{expected} local_release=v{local}"
        )
    return expected


def _remote_hash(base: str, remote: str) -> tuple[str, str]:
    return remote, hashlib.sha256(fetch_bytes(base, remote, timeout=FETCH_TIMEOUT_SECONDS)).hexdigest()


def probe_origin(name: str, base: str, expected_release: int) -> dict[str, object]:
    try:
        source = fetch_text(base, "release-version.js", timeout=FETCH_TIMEOUT_SECONDS)
        match = re.search(r"const RELEASE = (\d+);", source)
        published = int(match.group(1)) if match else -1
        if published != expected_release:
            return {
                "origin": name,
                "ready": False,
                "reason": f"published-v{published}-expected-v{expected_release}",
            }

        expected_hashes = {remote: local_hash(local) for local, remote in CRITICAL_ASSETS}
        actual_hashes: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_FETCHES, len(expected_hashes))) as pool:
            futures = {
                pool.submit(_remote_hash, base, remote): remote for remote in expected_hashes
            }
            for future in as_completed(futures):
                remote, digest = future.result()
                actual_hashes[remote] = digest
        mismatches = sorted(
            remote for remote, expected in expected_hashes.items() if actual_hashes.get(remote) != expected
        )
        if mismatches:
            return {
                "origin": name,
                "ready": False,
                "reason": "content-mismatch",
                "mismatches": mismatches,
            }
        return {
            "origin": name,
            "ready": True,
            "reason": "byte-identical",
            "asset_count": len(expected_hashes),
        }
    except Exception as exc:  # network state is reported, not hidden
        return {
            "origin": name,
            "ready": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }


def verify_shell_once(name: str, base: str, expected_release: int) -> None:
    expected = expected_shell()
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = {
            "index": pool.submit(fetch_text, base, "", FETCH_TIMEOUT_SECONDS),
            "app": pool.submit(fetch_text, base, "app.js", FETCH_TIMEOUT_SECONDS),
            "pwa": pool.submit(fetch_text, base, "pwa.js", FETCH_TIMEOUT_SECONDS),
            "worker": pool.submit(fetch_text, base, "service-worker.js", FETCH_TIMEOUT_SECONDS),
            "manifest": pool.submit(fetch_text, base, "service-worker-assets.generated.js", FETCH_TIMEOUT_SECONDS),
        }
        values = {key: future.result() for key, future in jobs.items()}

    index = values["index"]
    app = values["app"]
    pwa = values["pwa"]
    worker = values["worker"]
    shell_manifest = values["manifest"]

    for marker in (
        '<script src="./release-version.js"></script>',
        expected["header_style"],
        expected["mobile_style"],
        "data-header-search-toggle",
        "data-header-search-popover",
        'data-filter-value="hoy"',
        'data-filter-value="manana"',
        'data-filter-value="fin-de-semana"',
    ):
        if marker not in index:
            raise SystemExit(f"DEPLOYMENT_SHELL_STALE origin={name} surface=index marker={marker}")

    for marker in (expected["header_module"], expected["mobile_module"]):
        if marker not in pwa:
            raise SystemExit(f"DEPLOYMENT_SHELL_STALE origin={name} surface=pwa marker={marker}")

    for marker in (
        "render-lifecycle.js",
        "card-experience.js",
        "image-quality-guard.js",
        "event-card-data-quality.mjs",
        "exhibition-groups.js",
        "public-presentation-guard.js",
        "sources-toggle.js",
    ):
        if marker not in app:
            raise SystemExit(f"DEPLOYMENT_SHELL_STALE origin={name} surface=app marker={marker}")

    if "service-worker-assets.generated.js" not in worker:
        raise SystemExit(f"DEPLOYMENT_SHELL_STALE origin={name} surface=worker manifest=missing")
    for marker in (
        expected["header_style"],
        expected["mobile_style"],
        expected["header_module"],
        expected["mobile_module"],
        "./agenda-runtime-state.mjs",
        "./render-lifecycle.js",
        "./card-experience.js",
        "./image-quality-guard.js",
        "./event-card-data-quality.mjs",
        "./exhibition-groups.js",
        "./public-presentation-guard.js",
        "./public-presentation-rules.mjs",
    ):
        if not manifest_has(shell_manifest, marker):
            raise SystemExit(
                f"DEPLOYMENT_SHELL_STALE origin={name} surface=manifest marker={canonical_manifest_asset(marker)}"
            )

    print(f"PUBLISHED_PWA_SHELL_OK origin={name} release=v{expected_release}")


def probe_all(expected_release: int) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=len(ORIGINS)) as pool:
        futures = {
            pool.submit(probe_origin, name, base, expected_release): name
            for name, base in ORIGINS.items()
        }
        for future in as_completed(futures):
            row = future.result()
            rows[str(row["origin"])] = row
    return rows


def assert_all_ready(expected_release: int) -> dict[str, dict[str, object]]:
    rows = probe_all(expected_release)
    missing = [name for name in ORIGINS if not rows.get(name, {}).get("ready")]
    if missing:
        details = "; ".join(f"{name}={rows.get(name)}" for name in missing)
        raise SystemExit(f"DEPLOYMENT_NOT_READY {details}")
    with ThreadPoolExecutor(max_workers=len(ORIGINS)) as pool:
        futures = [
            pool.submit(verify_shell_once, name, base, expected_release)
            for name, base in ORIGINS.items()
        ]
        for future in as_completed(futures):
            future.result()
    for name in ORIGINS:
        print(
            f"PRODUCTION_ORIGIN_PARITY_OK origin={name} release=v{expected_release} assets={len(CRITICAL_ASSETS)}"
        )
    return rows


def wait_until_ready(expected_release: int, timeout_seconds: int, poll_seconds: float) -> tuple[dict[str, dict[str, object]], float]:
    started = time.monotonic()
    deadline = started + timeout_seconds
    attempt = 0
    last: dict[str, dict[str, object]] = {}
    while True:
        attempt += 1
        last = probe_all(expected_release)
        pending = [name for name in ORIGINS if not last.get(name, {}).get("ready")]
        elapsed = time.monotonic() - started
        if not pending:
            rows = assert_all_ready(expected_release)
            print(
                f"DEPLOYMENT_READY release=v{expected_release} attempts={attempt} elapsed_seconds={elapsed:.2f} origins={','.join(ORIGINS)}"
            )
            return rows, elapsed
        if time.monotonic() >= deadline:
            details = "; ".join(f"{name}={last.get(name)}" for name in pending)
            raise SystemExit(
                f"DEPLOYMENT_READINESS_TIMEOUT release=v{expected_release} timeout_seconds={timeout_seconds} pending={','.join(pending)} details={details}"
            )
        print(
            f"DEPLOYMENT_PENDING release=v{expected_release} attempt={attempt} elapsed_seconds={elapsed:.2f} pending={','.join(pending)}"
        )
        time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))


def write_evidence(path: Path, *, candidate_sha: str, release: int, mode: str, rows: dict[str, dict[str, object]], elapsed: float) -> None:
    payload = {
        "schema_version": "1.0.0",
        "candidate_sha": candidate_sha,
        "release": release,
        "mode": mode,
        "ready_at": utc_now(),
        "elapsed_seconds": round(elapsed, 3),
        "origins": rows,
        "state": "deployment_ready",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded, SHA-pinned readiness gate for GitHub Pages and Cloudflare.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--wait", action="store_true", help="Wait once, in parallel, for both production origins.")
    mode.add_argument("--assert-ready", action="store_true", help="One-shot assertion; never sleeps or retries.")
    parser.add_argument("--candidate-sha", default=os.getenv("GITHUB_SHA") or "")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.timeout_seconds <= 0 or args.timeout_seconds > DEFAULT_TIMEOUT_SECONDS:
        raise SystemExit(
            f"DEPLOYMENT_READINESS_BUDGET_INVALID timeout={args.timeout_seconds} max={DEFAULT_TIMEOUT_SECONDS}"
        )
    if args.poll_seconds <= 0:
        raise SystemExit("DEPLOYMENT_READINESS_POLL_INVALID")

    release = validate_candidate(args.candidate_sha)
    started = time.monotonic()
    if args.wait:
        rows, elapsed = wait_until_ready(release, args.timeout_seconds, args.poll_seconds)
        mode_name = "wait"
    else:
        rows = assert_all_ready(release)
        elapsed = time.monotonic() - started
        mode_name = "assert-ready"
        print(
            f"DEPLOYMENT_READY_ASSERTED release=v{release} elapsed_seconds={elapsed:.2f} origins={','.join(ORIGINS)}"
        )
    write_evidence(
        Path(args.output),
        candidate_sha=args.candidate_sha,
        release=release,
        mode=mode_name,
        rows=rows,
        elapsed=elapsed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
