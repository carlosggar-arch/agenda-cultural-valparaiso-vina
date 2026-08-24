from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLISH = ROOT / ".github" / "workflows" / "publish.yml"
READINESS = ROOT / "app" / "scripts" / "deployment_readiness.py"


def job_block(text: str, job: str, next_job: str | None) -> str:
    start = text.index(f"  {job}:\n")
    end = text.index(f"\n  {next_job}:\n", start) if next_job else len(text)
    return text[start:end]


def timeout_minutes(block: str) -> int:
    match = re.search(r"^    timeout-minutes:\s*(\d+)\s*$", block, flags=re.M)
    if not match:
        raise AssertionError("job timeout is missing")
    return int(match.group(1))


def main() -> None:
    publish = PUBLISH.read_text(encoding="utf-8")
    readiness = READINESS.read_text(encoding="utf-8")
    sync = job_block(publish, "sync-cloudflare", "production-smoke")
    smoke = job_block(publish, "production-smoke", "refresh-open-release-prs")

    assert "CANDIDATE_SHA: ${{ github.sha }}" in publish, "production runs must be pinned to their triggering SHA"
    assert 'git merge --no-edit "$CANDIDATE_SHA"' in sync, "deployment branch must merge the exact candidate"
    assert "git reset --hard origin/main" not in publish, "production verification must never jump to a newer main"
    assert "git merge --no-edit origin/main" not in publish, "publication must not silently adopt a later main"
    assert "ref: ${{ github.sha }}" in smoke, "production smoke checkout must be immutable"
    assert 'test "$(git rev-parse HEAD)" = "$CANDIDATE_SHA"' in smoke

    assert timeout_minutes(sync) <= 3, "deployment synchronization SLA exceeded"
    assert timeout_minutes(smoke) <= 7, "complete visual certification SLA exceeded"
    assert "timeout-minutes: 28" not in publish, "legacy 28-minute certification timeout returned"

    assert publish.count("--wait \\") == 1, "there must be exactly one deployment wait"
    assert publish.count("--assert-ready \\") == 1, "post-readiness validation must be one-shot"
    assert "--timeout-seconds 90" in sync, "deployment wait must be bounded to 90 seconds"
    assert "production_pwa_smoke.py http" not in publish, "legacy sequential HTTP wait must not run in publish.yml"
    assert "PRODUCTION_PROBES_PARALLEL_OK groups=4" in smoke, "independent production probes must remain parallel"
    for probe in (
        "production_admin_staging_smoke.py",
        "production_series_contract.py",
        "production_browser_selenium_smoke.py",
        "production_warm_start_smoke.py",
        "test_web_pwa_visibility_parity.py",
    ):
        assert probe in smoke, f"production probe disappeared: {probe}"

    assert "DEFAULT_TIMEOUT_SECONDS = 90" in readiness
    assert "ThreadPoolExecutor" in readiness, "origin readiness must be concurrent"
    assert "probe_all" in readiness and "wait_until_ready" in readiness
    assert "DEPLOYMENT_READINESS_TIMEOUT" in readiness
    assert "DEPLOYMENT_READY_ASSERTED" in readiness
    assert "timeout_seconds > DEFAULT_TIMEOUT_SECONDS" in readiness, "callers must not raise the bounded wait budget"

    assert 'if [[ "$head_sha" != "$CANDIDATE_SHA" ]]' in smoke, "certificate writer must reject a mutated head"
    assert "state/production-certifications" in smoke, "immutable certification history must remain the final writer target"

    print(
        "PRODUCTION_CERTIFICATION_LATENCY_CONTRACT_OK "
        "candidate_sha=immutable wait_budget=90s sync_timeout=3m smoke_timeout=7m parallel_probe_groups=4"
    )


if __name__ == "__main__":
    main()
