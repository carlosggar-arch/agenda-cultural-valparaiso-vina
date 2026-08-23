from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", default="actions-budget-report.json")
    args = parser.parse_args()
    policy = json.loads((ROOT / ".github/actions-budget.json").read_text(encoding="utf-8"))
    request = urllib.request.Request(
        f"https://api.github.com/repos/{args.repository}/actions/runs?per_page=100",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "vivamos-ci-budget"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        runs = json.load(response).get("workflow_runs", [])
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
    recent = [run for run in runs if dt.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")) >= cutoff]
    report = {
        "status": "warning" if len(recent) > policy["weekly_run_warning"] else "ok",
        "weekly_runs_observed": len(recent),
        "weekly_run_warning": policy["weekly_run_warning"],
        "by_workflow": dict(Counter(run["name"] for run in recent)),
        "note": "API page is capped at 100; reaching the cap is itself a budget warning.",
    }
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ACTIONS_BUDGET", json.dumps(report, ensure_ascii=False))
    if report["status"] == "warning":
        print(f"::warning::Actions weekly run budget exceeded or API cap reached: {len(recent)}")


if __name__ == "__main__":
    main()
