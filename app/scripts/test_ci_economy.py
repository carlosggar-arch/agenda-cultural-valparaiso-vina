from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
EXPECTED = {"pr-fast.yml", "pr-release.yml", "source-validation.yml", "publish.yml", "scheduled-audit.yml"}


def trigger_block(text: str) -> str:
    return text.split("permissions:", 1)[0]


def main() -> None:
    paths = sorted(WORKFLOWS.glob("*.yml"))
    names = {path.name for path in paths}
    assert names == EXPECTED, f"CI_TOPOLOGY_DRIFT expected={sorted(EXPECTED)} actual={sorted(names)}"
    texts = {path.name: path.read_text(encoding="utf-8") for path in paths}
    for name in ("pr-fast.yml", "pr-release.yml", "source-validation.yml"):
        text = texts[name]
        assert "cancel-in-progress: true" in text, f"{name} must cancel obsolete PR runs"
        assert "push:" not in trigger_block(text), f"{name} must not duplicate PR validation after merge"
    publish = texts["publish.yml"]
    assert "pull_request:" not in trigger_block(publish)
    assert "push:" in trigger_block(publish) and "branches: [main]" in trigger_block(publish)
    assert sum("selenium==" in text for name, text in texts.items() if name.startswith("pr-")) == 1
    assert texts["scheduled-audit.yml"].count("- cron:") == 1
    assert "if: failure()" in texts["source-validation.yml"]
    assert "if: failure()" in texts["pr-release.yml"]
    assert "--profile pr-fast-all" in texts["pr-fast.yml"]
    assert "--profile multi-city" not in texts["pr-release.yml"]
    assert "name: release-guard" in texts["pr-release.yml"], "branch-protection context must remain stable"
    budget = json.loads((ROOT / ".github/actions-budget.json").read_text(encoding="utf-8"))
    assert budget["workflow_count"] == len(paths)
    assert budget["runs_per_pr_update_max"] <= 3
    assert budget["browser_suites_per_pr"] == 1
    assert budget["automatic_publish_runs_per_merge"] == 1
    print("CI_ECONOMY_OK workflows=5 pr_runs_max=3 browser_suites=1 publish_runs=1")


if __name__ == "__main__":
    main()
