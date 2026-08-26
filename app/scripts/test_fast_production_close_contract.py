from pathlib import Path

from runtime_release_guard import classify_release_change, root_index_runtime_changed


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
DATASET_VALIDATOR = (ROOT / "app/scripts/fast_close_dataset_validation.py").read_text(encoding="utf-8")
PR_FAST = (ROOT / ".github/workflows/pr-fast.yml").read_text(encoding="utf-8")


def main() -> None:
    sync = WORKFLOW.split("  sync-cloudflare:\n", 1)[1].split("  production-smoke:\n", 1)[0]
    production = WORKFLOW.split("  production-smoke:\n", 1)[1].split("  refresh-open-release-prs:\n", 1)[0]

    assert "Push synchronized deployment branch" in sync
    assert "Fast-close changed dataset freshness and identity" in sync
    assert "Fast-close deterministic runtime contracts" in sync
    assert "Wait once for both production origins in parallel" in sync
    assert "deployment_readiness.py" in sync
    assert "fast_close_dataset_validation.py --base-ref" in sync
    assert "python app/scripts/runtime_release_guard.py" in sync
    assert '--base-ref "$before"' in sync
    assert '--head-ref "$CANDIDATE_SHA"' in sync
    assert "--wait" in sync
    assert "--timeout-seconds 90" in sync
    assert "--poll-seconds 2" in sync
    assert "DEPLOYMENT_READY" in sync
    assert "DEPLOYED_BYTE_VERIFIED" in sync
    assert "visual=pending" in sync
    assert "PUBLICATION_FAST_CLOSE_VERIFIED" not in sync
    assert sync.index("Push synchronized deployment branch") < sync.index("DEPLOYMENT_READY")
    assert sync.index("DEPLOYMENT_READY") < sync.index("DEPLOYED_BYTE_VERIFIED")

    # Dataset identity and metadata coherence remain strict, but the six-hour
    # freshness window is now scoped to actual source regeneration: a semantic
    # rewrite with the same generated_at must not impersonate a fresh ingest.
    for marker in (
        "FAST_CLOSE_IDS_INVALID",
        "FAST_CLOSE_COUNT_MISMATCH",
        "FAST_CLOSE_METADATA_MISSING",
        "FAST_CLOSE_PUBLICATION_DATE_MISMATCH",
        "FAST_CLOSE_DATASET_STALE",
        "generated_at",
        "ZoneInfo",
        "previous_generated_at",
    ):
        assert marker in DATASET_VALIDATOR
    assert "current_generated_at != previous_generated_at" in DATASET_VALIDATOR
    assert "if require_fresh:" in DATASET_VALIDATOR
    assert "age_hours > 6" in DATASET_VALIDATOR
    assert "generation_changed=" in DATASET_VALIDATOR

    # Permanent routes are part of the deployed bytes. Stage 3.1 is the final
    # page writer (it reuses generate_event_pages as a renderer), so both PR CI
    # and production fast-close must reproduce that final layer and require a
    # clean diff rather than validating an intermediate template.
    assert '"scripts/stage31_site_generator.py"' in DATASET_VALIDATOR
    assert "FAST_CLOSE_PERMANENT_PAGES_OK writer=stage31" in DATASET_VALIDATOR
    assert "FAST_CLOSE_PERMANENT_PAGES_STALE" in DATASET_VALIDATOR
    assert "python scripts/stage31_site_generator.py" in PR_FAST
    assert "git diff --exit-code -- evento sitemap.xml" in PR_FAST
    generated_step = PR_FAST.split("- name: Validate final generated pages when affected", 1)[1]
    assert "python scripts/generate_event_pages.py" not in generated_step

    # The root landing is partly runtime shell and partly dataset-owned SEO.
    # Only the explicitly marked Stage 3.1 JSON-LD payload may vary without a
    # PWA release bump; any surrounding shell change must remain protected.
    before_index = (
        '<html><head><script id="stage31-root-jsonld" type="application/ld+json">'
        '{"count":205}</script></head><body class="shell">Agenda</body></html>'
    )
    data_only_index = (
        '<html><head><script id="stage31-root-jsonld" type="application/ld+json">'
        '{"count":198}</script></head><body class="shell">Agenda</body></html>'
    )
    runtime_index = (
        '<html><head><script id="stage31-root-jsonld" type="application/ld+json">'
        '{"count":198}</script></head><body class="shell changed">Agenda</body></html>'
    )
    assert root_index_runtime_changed(before_index, data_only_index) is False
    assert root_index_runtime_changed(before_index, runtime_index) is True

    generated_only = classify_release_change(
        ["agenda_web.json", "index.html"],
        before_index=before_index,
        after_index=data_only_index,
    )
    assert generated_only.runtime_changed == ()
    assert generated_only.generated_only == ("index.html",)
    assert generated_only.violation is False

    shell_change = classify_release_change(
        ["index.html"],
        before_index=before_index,
        after_index=runtime_index,
    )
    assert shell_change.runtime_changed == ("index.html",)
    assert shell_change.violation is True

    js_without_release = classify_release_change(["app/app.js"])
    assert js_without_release.runtime_changed == ("app/app.js",)
    assert js_without_release.violation is True

    js_with_release = classify_release_change(["app/app.js", "app/release-version.js"])
    assert js_with_release.release_changed is True
    assert js_with_release.violation is False

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

    print("FAST_PRODUCTION_CLOSE_CONTRACT_OK readiness=parallel wait_budget=90s candidate_sha=immutable release_guard=generated-data-aware permanent_pages=stage31")


if __name__ == "__main__":
    main()
