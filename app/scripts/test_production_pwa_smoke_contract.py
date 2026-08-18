from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/production-pwa-smoke.yml").read_text(encoding="utf-8")
SMOKE = (ROOT / "app/scripts/production_pwa_smoke.py").read_text(encoding="utf-8")


def block(start_marker: str, end_marker: str | None = None) -> str:
    start = WORKFLOW.index(start_marker)
    if end_marker is None:
        return WORKFLOW[start:]
    end = WORKFLOW.index(end_marker, start)
    return WORKFLOW[start:end]


def main() -> None:
    triggers = WORKFLOW.split("permissions:", 1)[0]
    assert '      - "app/**"' not in triggers, "Production smoke must not wake for every app file"
    assert '      - "app/*.js"' in triggers
    assert '      - "app/*.css"' in triggers
    assert '      - "app/*.html"' in triggers
    assert '      - "app/*.webmanifest"' in triggers
    assert '      - "app/scripts/production_pwa_smoke.py"' in triggers
    assert '      - ".github/workflows/production-pwa-smoke.yml"' in triggers

    assert "pr-contract:" in WORKFLOW
    assert "production-smoke:" in WORKFLOW
    pr = block("  pr-contract:\n", "  production-smoke:\n")
    production = block("  production-smoke:\n")

    assert "if: github.event_name == 'pull_request'" in pr
    assert "python app/scripts/production_pwa_smoke.py local" in pr
    assert "python app/scripts/test_production_pwa_smoke_contract.py" in pr
    assert "production_pwa_smoke.py http" not in pr
    assert "production_pwa_smoke.py browser" not in pr

    assert "if: github.event_name != 'pull_request'" in production
    assert "Require release bump for runtime pushes" in production
    assert "app/release-version.js" in production
    assert "python app/scripts/production_pwa_smoke.py http" in production
    assert "python app/scripts/production_pwa_smoke.py browser" in production
    assert "timeout-minutes: 8" in production

    # Production assertions must derive current asset revisions from source,
    # rather than fossilising version strings inside the smoke implementation.
    for stale in ("20260817-brandicon1", "20260817-topcontrols4", "hero-v4-mobile-direct-actions"):
        assert stale not in SMOKE, f"Hard-coded presentation revision returned to production smoke: {stale}"

    assert "attempts: int = 30" in SMOKE
    assert "interval: int = 10" in SMOKE
    assert '("valparaiso", "Valparaíso / Viña del Mar", 390, 844)' in SMOKE
    assert '("gijon", "Gijón / Xixón", 1280, 900)' in SMOKE
    assert "--disable-background-networking" in SMOKE
    assert "after retry" in SMOKE

    print("PRODUCTION_PWA_SMOKE_CONTRACT_OK")


if __name__ == "__main__":
    main()
