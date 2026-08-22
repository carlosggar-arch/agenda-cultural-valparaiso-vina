from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "tests" / "contract-topology.json"


def load_topology() -> dict:
    return json.loads(TOPOLOGY.read_text(encoding="utf-8"))


def command_for_owner(owner: str) -> list[str]:
    if owner.endswith(".py"):
        return [sys.executable, owner]
    if owner.endswith((".mjs", ".js")):
        return ["node", owner]
    raise ValueError(f"Contract owner is not directly executable: {owner}")


def run_contract(contract_id: str, contracts: dict[str, dict]) -> None:
    if contract_id not in contracts:
        raise KeyError(f"Unknown contract: {contract_id}")
    entry = contracts[contract_id]
    owner = entry["owner"]
    command = command_for_owner(owner)
    print(f"CONTRACT_START {contract_id} owner={owner}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
    print(f"CONTRACT_OK {contract_id}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run canonical product contracts by topology id/profile")
    parser.add_argument("--contract", action="append", default=[], help="Canonical contract id; repeatable")
    parser.add_argument("--profile", action="append", default=[], help="Named runner profile; repeatable")
    parser.add_argument("--list", action="store_true", help="List executable contracts and profiles")
    args = parser.parse_args()

    topology = load_topology()
    contracts = {entry["id"]: entry for entry in topology.get("contracts", [])}
    profiles = topology.get("runner_profiles", {})

    if args.list:
        print("PROFILES")
        for name, ids in sorted(profiles.items()):
            print(f"  {name}: {', '.join(ids)}")
        print("CONTRACTS")
        for contract_id, entry in sorted(contracts.items()):
            owner = entry.get("owner", "")
            executable = owner.endswith((".py", ".mjs", ".js"))
            print(f"  {contract_id}: {owner}{'' if executable else ' [workflow-only]'}")
        return

    selected: list[str] = []
    for profile in args.profile:
        if profile not in profiles:
            parser.error(f"unknown profile: {profile}")
        selected.extend(profiles[profile])
    selected.extend(args.contract)

    if not selected:
        parser.error("select at least one --profile or --contract")

    ordered_unique = list(dict.fromkeys(selected))
    for contract_id in ordered_unique:
        run_contract(contract_id, contracts)

    print(f"CONTRACT_RUNNER_OK count={len(ordered_unique)}", flush=True)


if __name__ == "__main__":
    main()
