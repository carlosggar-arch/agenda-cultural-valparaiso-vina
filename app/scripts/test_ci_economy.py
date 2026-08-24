from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
EXPECTED = {
    "pr-fast.yml",
    "pr-release.yml",
    "source-validation.yml",
    "publish.yml",
    "scheduled-audit.yml",
    "production-certification-watchdog.yml",
}


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
    watchdog = texts["production-certification-watchdog.yml"]
    watchdog_triggers = trigger_block(watchdog)
    assert "workflow_run:" in watchdog_triggers
    assert 'workflows: ["Publish and production verification"]' in watchdog_triggers
    assert "types: [completed]" in watchdog_triggers
    assert "pull_request:" not in watchdog_triggers and "push:" not in watchdog_triggers
    assert "actions: read" in watchdog and "contents: read" in watchdog
    assert "contents: write" not in watchdog
    assert "PRODUCTION_UNCERTIFIED" in watchdog
    assert "production_certification_watchdog.py" in watchdog
    assert sum("-r requirements-ci.txt" in text for name, text in texts.items() if name.startswith("pr-")) == 1
    assert (ROOT / "requirements-ci.txt").read_text(encoding="utf-8").strip() == "selenium==4.35.0"
    assert (ROOT / "requirements-image-cache.txt").read_text(encoding="utf-8").strip() == "Pillow==12.3.0"
    assert "-r requirements-image-cache.txt" in texts["source-validation.yml"]
    assert sum("-r requirements-image-cache.txt" in text for text in texts.values()) == 1
    assert texts["scheduled-audit.yml"].count("- cron:") == 1
    assert "pull_request:" not in trigger_block(texts["scheduled-audit.yml"])
    assert "if: failure()" in texts["source-validation.yml"]
    assert "test_source_health_audit.py" in texts["source-validation.yml"]
    assert '".github/workflows/scheduled-audit.yml"' in texts["source-validation.yml"]
    assert "if: failure()" in texts["pr-release.yml"]
    assert "run_impacted_contracts.py" in texts["pr-fast.yml"]
    assert "run_contracts.py --profile pr-fast-all" not in texts["pr-fast.yml"]
    assert "--profile multi-city" not in texts["pr-release.yml"]
    assert "name: release-guard" in texts["pr-release.yml"], "branch-protection context must remain stable"
    assert "  sync-cloudflare:" in publish and "  production-smoke:" in publish
    assert "    needs: sync-cloudflare" in publish
    for name, workflow in texts.items():
        assert "actions/checkout@v4" not in workflow, f"{name} still uses the Node 20 checkout action"
        assert "actions/setup-python@v5" not in workflow, f"{name} still uses the Node 20 setup-python action"
        assert "actions/upload-artifact@v4" not in workflow, f"{name} still uses the Node 20 upload action"
    budget = json.loads((ROOT / ".github/actions-budget.json").read_text(encoding="utf-8"))
    assert budget["workflow_count"] == len(paths)
    assert budget["runs_per_pr_update_max"] <= 3
    assert budget["browser_suites_per_pr"] == 1
    assert budget["automatic_publish_runs_per_merge"] == 1
    assert budget["automatic_certification_watchdog_runs_per_publish"] == 1
    print("CI_ECONOMY_OK workflows=6 pr_runs_max=3 browser_suites=1 publish_runs=1 certification_watchdog_runs=1")


if __name__ == "__main__":
    main()
