from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "tests" / "contract-topology.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run canonical browser scenarios")
    parser.add_argument("--scenario", action="append", default=[], help="Scenario id; repeatable")
    parser.add_argument("--all", action="store_true", help="Run all canonical browser scenarios")
    args = parser.parse_args()

    topology = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
    contracts = {entry["id"]: entry for entry in topology.get("contracts", [])}
    scenarios = topology.get("browser_scenarios", {})

    selected = list(scenarios) if args.all else args.scenario
    if not selected:
        parser.error("select --all or at least one --scenario")

    contract_ids: list[str] = []
    for scenario in selected:
        if scenario not in scenarios:
            parser.error(f"unknown browser scenario: {scenario}")
        contract_ids.extend(scenarios[scenario])

    for contract_id in dict.fromkeys(contract_ids):
        entry = contracts.get(contract_id)
        if not entry or entry.get("layer") != "browser":
            raise AssertionError(f"scenario references non-browser contract: {contract_id}")
        owner = entry["owner"]
        if not owner.endswith(".py"):
            raise AssertionError(f"browser owner must be Python executable: {contract_id} -> {owner}")
        command = [sys.executable, owner, *entry.get("runner_args", [])]
        print(f"BROWSER_CONTRACT_START {contract_id} owner={owner}", flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
        print(f"BROWSER_CONTRACT_OK {contract_id}", flush=True)

    print(f"BROWSER_SCENARIOS_OK scenarios={len(selected)} contracts={len(dict.fromkeys(contract_ids))}", flush=True)


if __name__ == "__main__":
    main()
