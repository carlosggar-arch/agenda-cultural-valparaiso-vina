from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENT_PAGES = (ROOT / ".github/workflows/event-pages.yml").read_text(encoding="utf-8")
FALLBACK = (ROOT / ".github/workflows/compose-valpo-dataset.yml").read_text(encoding="utf-8")

REQUIRED_MAIN_STEPS = [
    "python app/scripts/refresh_museo_maritimo.py",
    "python app/scripts/refresh_balmaceda_valpo_bounded.py",
    "python app/scripts/refresh_visitavina_fonck.py",
    "python app/scripts/refresh_visitavina_estadio_espanol.py",
    "python app/scripts/refresh_portaltickets_editorial.py",
    "python app/scripts/refresh_valpocultura_zero_recovery.py",
    "python app/scripts/refresh_priority_zero_monitors.py",
    "python app/scripts/apply_title_quality_guard.py",
    "python app/scripts/apply_content_quality_guard.py",
    "python app/scripts/refresh_quality_diagnostics.py",
    "python app/scripts/apply_source_coverage_overrides.py",
    "python app/scripts/apply_balmaceda_coverage.py",
    "python app/scripts/apply_fonck_coverage.py",
    "python app/scripts/apply_estadio_espanol_coverage.py",
]


def main() -> None:
    positions = []
    for marker in REQUIRED_MAIN_STEPS:
        index = EVENT_PAGES.find(marker)
        assert index >= 0, f"Missing atomic publication step: {marker}"
        positions.append(index)
    assert positions == sorted(positions), "Supplement steps are not in the intended publication order"
    commit_index = EVENT_PAGES.find("git commit -m \"Actualiza fuentes, diagnósticos y fichas permanentes\"")
    assert commit_index > max(positions), "Publication commit happens before supplemental composition finishes"
    assert "app/data/quality/visitavina-fonck.json" in EVENT_PAGES
    assert "app/data/quality/visitavina-estadio-espanol.json" in EVENT_PAGES
    assert "app/data/quality/balmaceda-valpo.json" in EVENT_PAGES
    assert "app/data/quality/content-quality.json" in EVENT_PAGES
    assert "push:" not in FALLBACK.split("permissions:", 1)[0], "Fallback composer must not auto-run on push"
    assert "workflow_dispatch:" in FALLBACK, "Fallback composer must remain manually runnable"
    print("ATOMIC_PUBLICATION_CONTRACT_OK")


if __name__ == "__main__":
    main()
