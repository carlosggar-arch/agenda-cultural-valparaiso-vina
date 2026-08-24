from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")


def main() -> None:
    sync = WORKFLOW.split("  sync-cloudflare:\n", 1)[1].split("  production-smoke:\n", 1)[0]
    production = WORKFLOW.split("  production-smoke:\n", 1)[1]

    assert "Push synchronized deployment branch" in sync
    assert "Fast-close changed dataset freshness and identity" in sync
    assert "Fast-close deterministic runtime contracts" in sync
    assert "Fast-close GitHub Pages and Cloudflare byte parity" in sync
    assert "DEPLOYED_BYTE_VERIFIED" in sync
    assert "visual=pending" in sync
    assert "PUBLICATION_FAST_CLOSE_VERIFIED" not in sync
    assert sync.index("Push synchronized deployment branch") < sync.index("DEPLOYED_BYTE_VERIFIED")

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

    assert "python app/scripts/production_pwa_smoke.py http" in sync
    assert "PRODUCTION_ORIGIN_PARITY_OK origin=github-pages" in sync
    assert "PRODUCTION_ORIGIN_PARITY_OK origin=cloudflare" in sync

    # Fast close is an earlier bounded decision, never a replacement for the
    # deeper browser/offline evidence.
    assert "production_browser_selenium_smoke.py" in production
    assert "production_warm_start_smoke.py" in production
    assert "test_web_pwa_visibility_parity.py" in production
    assert "PRODUCTION_RELEASE_VERIFIED" in production

    print("FAST_PRODUCTION_CLOSE_CONTRACT_OK")


if __name__ == "__main__":
    main()
