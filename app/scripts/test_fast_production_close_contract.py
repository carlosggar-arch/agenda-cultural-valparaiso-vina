from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")


def main() -> None:
    sync = WORKFLOW.split("  sync-cloudflare:\n", 1)[1].split("  production-smoke:\n", 1)[0]
    production = WORKFLOW.split("  production-smoke:\n", 1)[1].split("  refresh-open-release-prs:\n", 1)[0]

    assert "Push synchronized deployment branch" in sync
    assert "Fast-close changed dataset freshness and identity" in sync
    assert "Fast-close deterministic runtime contracts" in sync
    assert "Wait once for both production origins in parallel" in sync
    assert "deployment_readiness.py" in sync
    assert "--wait" in sync
    assert "--timeout-seconds 90" in sync
    assert "--poll-seconds 2" in sync
    assert "DEPLOYMENT_READY" in sync
    assert "DEPLOYED_BYTE_VERIFIED" in sync
    assert "visual=pending" in sync
    assert "PUBLICATION_FAST_CLOSE_VERIFIED" not in sync
    assert sync.index("Push synchronized deployment branch") < sync.index("DEPLOYMENT_READY")
    assert sync.index("DEPLOYMENT_READY") < sync.index("DEPLOYED_BYTE_VERIFIED")

    strict = sync.split("              if require_fresh:\n", 1)[1].split("\n              print(", 1)[0]
    assert "FAST_CLOSE_METADATA_MISSING" in strict
    assert "FAST_CLOSE_PUBLICATION_DATE_MISMATCH" in strict
    assert "FAST_CLOSE_DATASET_STALE" in strict
    assert "generated_at" in strict
    assert "ZoneInfo" in sync

    before_strict = sync.split("              if require_fresh:\n", 1)[0]
    assert "FAST_CLOSE_IDS_INVALID" in before_strict
    assert "FAST_CLOSE_COUNT_MISMATCH" in before_strict
    assert "FAST_CLOSE_PUBLICATION_DATE_MISMATCH" not in before_strict
    assert "FAST_CLOSE_DATASET_STALE" not in before_strict

    # Deployment propagation has one bounded retry loop shared by both origins.
    # The old per-origin sequential HTTP waiter must never return here.
    assert "python app/scripts/production_pwa_smoke.py http" not in WORKFLOW
    assert WORKFLOW.count("--wait \\") == 1
    assert "PRODUCTION_ORIGIN_PARITY_OK origin=github-pages" in sync
    assert "PRODUCTION_ORIGIN_PARITY_OK origin=cloudflare" in sync

    # The post-readiness job may re-check bytes once, but it must not wait again
    # and it must stay pinned to the triggering candidate SHA.
    assert "Re-assert deployed bytes without waiting" in production
    assert "--assert-ready" in production
    assert "--wait" not in production
    assert "git reset --hard origin/main" not in WORKFLOW
    assert 'test "$(git rev-parse HEAD)" = "$CANDIDATE_SHA"' in production

    # Fast close remains only the deployment readiness decision. The complete
    # certification still requires all deeper browser/offline/semantic evidence.
    assert "production_browser_selenium_smoke.py" in production
    assert "production_warm_start_smoke.py" in production
    assert "test_web_pwa_visibility_parity.py" in production
    assert "production_series_contract.py" in production
    assert "production_admin_staging_smoke.py" in production
    assert "PRODUCTION_PROBES_PARALLEL_OK groups=4" in production
    assert "PRODUCTION_RELEASE_VERIFIED" in production

    print("FAST_PRODUCTION_CLOSE_CONTRACT_OK readiness=parallel wait_budget=90s candidate_sha=immutable")


if __name__ == "__main__":
    main()
