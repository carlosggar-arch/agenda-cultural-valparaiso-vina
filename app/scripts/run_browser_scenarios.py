from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "tests" / "contract-topology.json"
HISTORICAL_DATASET_REF = "54c8a58e17b283bc2f1fe7303738bc00fbc75e61"
HISTORICAL_DATASET_CONTRACTS = frozenset({"app/scripts/test_runtime_browser.py"})


def run_browser_contract(command: list[str], owner: str) -> None:
    """Run one browser contract, isolating historical-data regressions from the live publication snapshot.

    The runtime browser suite contains a Caleta de Historias regression whose source event
    legitimately expired after 22 Aug 2026. Production datasets must continue pruning expired
    events, so that regression is executed against the immutable repository snapshot that still
    contains the real official record. The candidate runtime code is otherwise unchanged, and
    the current dataset is restored immediately after the contract.
    """
    if owner not in HISTORICAL_DATASET_CONTRACTS:
        subprocess.run(command, cwd=ROOT, check=True)
        return

    dataset_path = ROOT / "agenda_web.json"
    candidate_dataset = dataset_path.read_bytes()
    try:
        historical_dataset = subprocess.check_output(
            ["git", "show", f"{HISTORICAL_DATASET_REF}:agenda_web.json"],
            cwd=ROOT,
        )
        dataset_path.write_bytes(historical_dataset)
        print(
            f"BROWSER_HISTORICAL_DATASET_FIXTURE owner={owner} ref={HISTORICAL_DATASET_REF}",
            flush=True,
        )
        subprocess.run(command, cwd=ROOT, check=True)
    finally:
        dataset_path.write_bytes(candidate_dataset)


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
        run_browser_contract(command, owner)
        print(f"BROWSER_CONTRACT_OK {contract_id}", flush=True)

    print(f"BROWSER_SCENARIOS_OK scenarios={len(selected)} contracts={len(dict.fromkeys(contract_ids))}", flush=True)


if __name__ == "__main__":
    main()
