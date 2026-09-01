from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
REQUIRED = (ROOT / ".github/workflows/pr-release.yml").read_text(encoding="utf-8")
TOPOLOGY = json.loads((ROOT / "tests/contract-topology.json").read_text(encoding="utf-8"))
SMOKE = (ROOT / "app/scripts/production_pwa_smoke.py").read_text(encoding="utf-8")
BROWSER_SMOKE = (ROOT / "app/scripts/production_browser_selenium_smoke.py").read_text(encoding="utf-8")
SEMANTIC_CAPABILITIES = (ROOT / "app/scripts/production_semantic_capabilities.py").read_text(encoding="utf-8")
WARM_SMOKE = (ROOT / "app/scripts/production_warm_start_smoke.py").read_text(encoding="utf-8")
PWA_PARITY = (ROOT / "app/scripts/test_web_pwa_visibility_parity.py").read_text(encoding="utf-8")
ATTESTATION = (ROOT / "app/scripts/production_release_attestation.py").read_text(encoding="utf-8")
APP = (ROOT / "app/app.js").read_text(encoding="utf-8")
PWA = (ROOT / "app/pwa.js").read_text(encoding="utf-8")
SOURCES = (ROOT / "app/sources-toggle.js").read_text(encoding="utf-8")
RUNTIME_RELEASE_GUARD = (ROOT / "app/scripts/runtime_release_guard.py").read_text(encoding="utf-8")


def block(start_marker: str, end_marker: str | None = None) -> str:
    start = WORKFLOW.index(start_marker)
    if end_marker is None:
        return WORKFLOW[start:]
    end = WORKFLOW.index(end_marker, start)
    return WORKFLOW[start:end]


def main() -> None:
    triggers = WORKFLOW.split("permissions:", 1)[0]
    assert "pull_request:" not in triggers, "Production smoke must be post-merge/manual only after D4"
    assert "push:" in triggers and "branches: [main]" in triggers
    assert "workflow_dispatch:" in triggers, "Production smoke must remain manually rerunnable against main"
    assert "GH_TOKEN: ${{ github.token }}" in WORKFLOW, "published squash attestation must receive authenticated PR metadata"
    assert WORKFLOW.count("pull-requests: read") >= 3, "every published-lineage job must retain read-only PR evidence access"
    assert '      - "app/**"' not in triggers, "Production smoke must not wake for every app file"
    for marker in (
        '      - "app/*.js"',
        '      - "app/*.mjs"',
        '      - "app/*.css"',
        '      - "app/*.html"',
        '      - "app/*.webmanifest"',
        '      - "assets/*.js"',
        '      - "assets/*.mjs"',
        '      - "index.html"',
        '      - "agenda_web.json"',
        '      - "app/data/gijon/agenda_web.json"',
        '      - "fuentes_publicas.json"',
        '      - "app/data/source-registry.json"',
        '      - "app/scripts/production_pwa_smoke.py"',
        '      - "app/scripts/production_browser_selenium_smoke.py"',
        '      - "app/scripts/production_warm_start_smoke.py"',
        '      - "app/scripts/test_web_pwa_visibility_parity.py"',
        '      - "app/scripts/production_release_attestation.py"',
        '      - "app/scripts/runtime_release_guard.py"',
        '      - ".github/workflows/publish.yml"',
    ):
        assert marker in triggers, f"Production smoke trigger missing: {marker}"

    assert "pr-contract:" not in WORKFLOW, "Local PR smoke must be owned by Required release guard after D4"
    assert "sync-cloudflare:" in WORKFLOW
    assert "production-smoke:" in WORKFLOW
    sync = block("  sync-cloudflare:\n", "  production-smoke:\n")
    production = block("  production-smoke:\n", "  refresh-open-release-prs:\n")

    # Publication is pinned to one immutable candidate. Release-delta enforcement
    # happens before deployment; production verification never jumps to a newer main.
    assert "CANDIDATE_SHA: ${{ github.sha }}" in WORKFLOW
    # The deployment branch keeps its history while adopting the immutable
    # candidate tree: checkout the candidate, then attach the previous
    # deployment head with an ``ours`` merge.  Assert the mechanics rather
    # than a human-facing step label so wording changes cannot weaken or break
    # this contract.
    assert "Create exact-tree handoff preserving deployment history" in sync
    assert "Checkout immutable deployment candidate" in sync
    assert "ref: ${{ github.sha }}" in sync
    assert "ref: cloudflare-preview" not in sync
    assert 'git checkout --detach "$CANDIDATE_SHA"' in sync
    assert "git merge --no-edit -s ours origin/cloudflare-preview" in sync
    assert "Require exact deployment-branch parity with candidate" in sync
    assert 'unexpected="$(git diff --name-only "$CANDIDATE_SHA" HEAD)"' in sync
    assert "Require release bump for runtime pushes" in sync
    assert "if: github.event_name == 'push'" in sync
    assert "app/release-version.js" in sync
    assert "python app/scripts/runtime_release_guard.py" in sync
    assert '--base-ref "$before"' in sync
    assert '--head-ref "$CANDIDATE_SHA"' in sync
    # Runtime extension ownership now lives in the dedicated guard rather than
    # being duplicated inline in the workflow. Keep that delegated contract
    # explicit so the preflight fails if either side drifts again.
    for marker in ("js|mjs|css|html|webmanifest", "RELEASE_VERSION", "RUNTIME_PATH", "RELEASE_RUNTIME_GUARD_BLOCKED"):
        assert marker in RUNTIME_RELEASE_GUARD, f"Runtime release guard contract missing: {marker}"
    assert "Validate Cloudflare build snapshot and exact release lineage" in sync
    assert 'release_finalizer.py --check-published --finalizer-ref "$CANDIDATE_SHA"' in sync
    assert "git reset --hard origin/main" not in WORKFLOW

    # The only bounded propagation wait is shared by both production origins.
    assert "Wait once for both production origins in parallel" in sync
    assert "deployment_readiness.py" in sync
    assert "--timeout-seconds 90" in sync
    assert "DEPLOYMENT_READY" in sync
    assert "DEPLOYED_BYTE_VERIFIED" in WORKFLOW
    assert "visual=pending" in WORKFLOW
    assert "PUBLICATION_FAST_CLOSE_VERIFIED" not in WORKFLOW

    # Deep certification runs against the exact published SHA and parallelizes
    # independent browser/offline/semantic probes after byte readiness.
    assert "Checkout immutable published candidate" in production
    assert "ref: ${{ github.sha }}" in production
    assert "Install browser timing dependency" in production
    assert "-r requirements-ci.txt" in production
    assert "cache-dependency-path: requirements-ci.txt" in production
    assert "Assert immutable candidate and local contracts" in production
    assert 'test "$(git rev-parse HEAD)" = "$CANDIDATE_SHA"' in production
    assert "python app/scripts/production_pwa_smoke.py local" in production
    assert "Re-assert deployed bytes without waiting" in production
    assert "--assert-ready" in production
    assert "--wait" not in production
    assert "Run independent production probes in parallel" in production
    assert "PRODUCTION_PROBES_PARALLEL_OK groups=4" in production
    assert "python app/scripts/production_browser_selenium_smoke.py" in production
    assert "python app/scripts/production_pwa_smoke.py browser" not in production
    assert "python app/scripts/production_pwa_smoke.py http" not in production
    assert "python app/scripts/production_warm_start_smoke.py" in production
    assert "python app/scripts/test_web_pwa_visibility_parity.py" in production
    assert "--production" in production and "--json-output" in production
    assert "Create auditable production release attestation" in production
    assert "python app/scripts/production_release_attestation.py" in production
    assert "production-release-attestation.json" in production
    assert "grep -q '^PRODUCTION_RELEASE_VERIFIED '" in production
    assert "Certify exact source-to-production chain" in production
    assert "production_release_chain.py" in production
    assert "Persist immutable production certification" in production
    assert "state/production-certifications" in production
    assert "production-release-verification-${{ github.run_id }}" in production
    assert "actions/upload-artifact@v6" in production
    assert "retention-days: 30" in production
    assert "timeout-minutes: 7" in production
    assert "timeout-minutes: 28" not in production

    contracts = {entry["id"]: entry for entry in TOPOLOGY["contracts"]}
    required_profile = TOPOLOGY["runner_profiles"]["required-release"]
    local_smoke = contracts["release.local-pwa-smoke"]
    assert local_smoke["owner"] == "app/scripts/production_pwa_smoke.py"
    assert local_smoke["runner_args"] == ["local"]
    assert local_smoke["workflow"] == ".github/workflows/pr-release.yml"
    assert "release.local-pwa-smoke" in required_profile
    assert "release.production-smoke-contract" in required_profile
    assert "architecture.public-presentation" in required_profile
    assert "python app/scripts/run_contracts.py --profile required-release" in REQUIRED
    assert "production_pwa_smoke.py http" not in REQUIRED
    assert "production_pwa_smoke.py browser" not in REQUIRED
    assert "production_warm_start_smoke.py" in REQUIRED, "Required gate must at least compile the warm-smoke owner"
    assert "production_release_attestation.py" in REQUIRED, "Required gate must compile the attestation owner"
    assert "test_production_release_attestation.py" in REQUIRED, "Required gate must execute the attestation unit contract"
    assert "test_web_pwa_visibility_parity.py --local" in REQUIRED, "Required gate must prove local live/cached exact-ID parity"
    assert "node --check app/sources-toggle.js" in REQUIRED

    for stale in ("20260817-brandicon1", "20260817-topcontrols4", "hero-v4-mobile-direct-actions"):
        assert stale not in SMOKE, f"Hard-coded presentation revision returned to production smoke: {stale}"

    assert '"github-pages": "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina/app/"' in SMOKE
    assert '"cloudflare": "https://vivamos.pages.dev/app/"' in SMOKE
    assert "CRITICAL_ASSETS" in SMOKE
    assert "hashlib.sha256" in SMOKE
    assert "attempts: int = 36" in SMOKE
    assert "interval: int = 10" in SMOKE
    assert "data-sources-toggle" in SMOKE
    assert 'data-filter-value="manana"' in SMOKE

    for marker in (
        '("valparaiso", "Valparaíso / Viña del Mar", 390, 844)',
        '("gijon", "Gijón / Xixón", 1280, 900)',
        "webdriver.Chrome",
        "WebDriverWait",
        'options.page_load_strategy = "eager"',
        "dataset.vivamosReady",
        "document.querySelectorAll('.event-card').length > 0",
        "[data-sources-toggle], [data-sources-fallback]",
        "PRODUCTION_COLD_LOAD_OK",
        "PRODUCTION_CITY_ROUNDTRIP_OK",
        "PRODUCTION_OFFICIAL_IMAGE_OK",
        "OFFICIAL_IMAGE_CASES",
        "image.naturalWidth",
        '("app",',
        '("web",',
        "q=Museo%20Baburizza",
        "vivamos-images-{origin}-{surface}-{attempt}",
        "driver.set_page_load_timeout(45)",
        "for attempt in range(1, 3)",
        "transport=selenium",
        "after retry",
    ):
        assert marker in BROWSER_SMOKE, f"Selenium cold-browser smoke contract missing: {marker}"
    evidence_poll = BROWSER_SMOKE.split("def image_evidence", 1)[1].split("def prepare_image_evidence", 1)[0]
    assert "scrollIntoView" not in evidence_poll, "Image readiness polling must not trigger repeated scroll/render churn"
    assert "scrollIntoView" not in BROWSER_SMOKE, "Official-image verification must not mutate WEB scroll state"
    assert "image.loading = 'eager'" in BROWSER_SMOKE
    assert "rect.width < 1 || rect.height < 1" in BROWSER_SMOKE
    assert "data-grouped-event-id" in BROWSER_SMOKE
    assert "image_diagnostics" in BROWSER_SMOKE
    assert "load_valpo_semantic_datasets" in BROWSER_SMOKE
    assert "load_gijon_semantic_datasets" in BROWSER_SMOKE
    assert "select_valpo_semantic_cases" in BROWSER_SMOKE
    assert "select_gijon_semantic_case" in BROWSER_SMOKE
    assert "PRODUCTION_SEMANTIC_DATASET_DIVERGENCE" in SEMANTIC_CAPABILITIES
    assert "active_schedule,canonical_title,official_provenance" in SEMANTIC_CAPABILITIES
    assert "--dump-dom" not in BROWSER_SMOKE, "Cold-browser production smoke must not regress to direct Chrome dump-dom"

    for marker in (
        'MOBILE_CITY = "valparaiso"',
        "MOBILE_WIDTH = 390",
        "MOBILE_HEIGHT = 844",
        'CACHE_MARKER_KEY = "vivamos-processed-pipeline-marker-valparaiso"',
        "READY_TIMEOUT_SECONDS = 20",
        "CACHE_WRITE_TIMEOUT_SECONDS = 15",
        "MAX_WARM_RATIO = 1.75",
        "MAX_WARM_EXTRA_SECONDS = 4.0",
        "webdriver.Chrome",
        "WebDriverWait",
        'options.page_load_strategy = "eager"',
        "dataset.vivamosReady",
        "document.querySelectorAll('.event-card').length > 0",
        "wait_for_processed_cache",
        "time.monotonic()",
        "PRODUCTION_WARM_REOPEN_OK",
        "processed_cache=ready",
        "cold_seconds",
        "warm_seconds",
    ):
        assert marker in WARM_SMOKE, f"Warm production smoke contract missing: {marker}"
    assert "profile_dom" not in WARM_SMOKE, "Warm timing must measure core-ready, not dump-dom completion"

    for marker in (
        'STATES = ("hoy", "7-dias", "todos")',
        'data-combined-when',
        "WEB_PWA_PRESENTATION_PARITY_OK",
        "WEB_PWA_PRESENTATION_MISMATCH",
        "WEB_PWA_VISIBILITY_REPORT_OK",
        "--json-output",
        '"ids": exact_ids',
        '"presentation": [',
        "Network.emulateNetworkConditions",
        "wait_service_worker",
        '"github-pages"',
        '"cloudflare"',
    ):
        assert marker in PWA_PARITY, f"Exact WEB/PWA parity smoke missing: {marker}"

    for marker in (
        "CRITICAL_ASSETS",
        "remote_hash_attestation",
        "hashlib.sha256(fetch_bytes(base, remote))",
        "validate_http_log",
        "validate_browser_log",
        "parse_warm_metrics",
        "validate_parity_report",
        "Cross-origin exact-ID mismatch",
        "PRODUCTION_RELEASE_VERIFIED",
        '"network_reverified": verify_network',
        '"release_id": bundle.get("release_id")',
        '"publication_state": "published_and_visually_verified"',
        "official_image_attestation",
        "OFFICIAL_IMAGE_EVENT_IDS",
        "PRODUCTION_OFFICIAL_IMAGE_OK",
    ):
        assert marker in ATTESTATION, f"Production release attestation missing: {marker}"

    for marker in ("sources-toggle.js", "community-source.js", "participation-footer.js"):
        assert marker in APP, f"app.js lost content module ownership: {marker}"
    for marker in ('"./sources-toggle.js', '"./community-source.js', '"./participation-footer.js'):
        assert marker not in PWA, f"pwa.js regained duplicate content module ownership: {marker}"

    assert "DIAGNOSTIC_SOURCE_META" not in SOURCES
    for marker in ("canonical_source_id", "eventCountsBySourceId", "runtimeById"):
        assert marker in SOURCES, f"Canonical source mapping missing: {marker}"

    print("PRODUCTION_PWA_SMOKE_CONTRACT_OK candidate_sha=immutable readiness=single_wait probes=parallel")


if __name__ == "__main__":
    main()
