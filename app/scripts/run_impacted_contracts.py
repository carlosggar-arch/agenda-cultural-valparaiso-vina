from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "tests/ci-domain-map.json"


def changed_files(base: str, head: str) -> list[str]:
    if not base:
        return ["app/app.js"]
    output = subprocess.check_output(["git", "diff", "--name-only", f"{base}...{head}"], cwd=ROOT, text=True)
    return [line for line in output.splitlines() if line]


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def is_relevant(path: str, config: dict) -> bool:
    return path in config["relevant_files"] or path.startswith(tuple(config["relevant_prefixes"]))


def select(paths: list[str], config: dict) -> tuple[list[str], list[str], bool]:
    domains: list[str] = []
    contracts: list[str] = []
    full = False
    relevant = [path for path in paths if is_relevant(path, config)]
    if any(matches(path, config["critical_web_app_patterns"]) for path in relevant):
        full = True
    for path in relevant:
        owner = next((entry for entry in config["domains"] if matches(path, entry["patterns"])), None)
        if owner is None:
            full = True
            domains.append("unknown")
            continue
        domains.append(owner["name"])
        if owner.get("profile") == "pr-fast-all":
            full = True
        contracts.extend(owner.get("contracts", []))
    return list(dict.fromkeys(domains)), list(dict.fromkeys(contracts)), full


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the canonical contracts affected by changed paths")
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    config = json.loads(MAP.read_text(encoding="utf-8"))
    paths = changed_files(args.base, args.head)
    domains, contracts, full = select(paths, config)
    print(f"CI_DOMAIN_PLAN domains={','.join(domains) or 'none'} full={str(full).lower()} contracts={len(contracts)}")
    if args.plan_only or not any(is_relevant(path, config) for path in paths):
        return
    command = [sys.executable, "app/scripts/run_contracts.py"]
    if full:
        command.extend(["--profile", "pr-fast-all"])
    else:
        for contract in contracts:
            command.extend(["--contract", contract])
    if len(command) == 2:
        print("CI_DOMAIN_NO_PRODUCT_CONTRACTS")
        return
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
