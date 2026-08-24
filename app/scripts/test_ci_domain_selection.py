from __future__ import annotations

import json
from pathlib import Path

from run_impacted_contracts import MAP, ROOT, is_relevant, matches, select


def main() -> None:
    config = json.loads(MAP.read_text(encoding="utf-8"))
    topology = json.loads((ROOT / "tests/contract-topology.json").read_text(encoding="utf-8"))
    known = {entry["id"] for entry in topology["contracts"]}
    for domain in config["domains"]:
        unknown = set(domain.get("contracts", [])) - known
        assert not unknown, f"{domain['name']} references unknown contracts: {sorted(unknown)}"
    tracked = [
        line for line in __import__("subprocess").check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        if is_relevant(line, config)
    ]
    uncovered = [path for path in tracked if not any(matches(path, entry["patterns"]) for entry in config["domains"])]
    assert not uncovered, f"CI_DOMAIN_UNCOVERED_PATHS: {uncovered[:20]}"
    domains, contracts, full = select(["app/image-resolver-core.mjs"], config)
    assert domains == ["images"] and "semantic.image-resolver" in contracts and not full
    domains, _, full = select(["app/service-worker.js"], config)
    assert full, "critical WEB/APP changes must force the complete fast suite"
    domains, _, full = select(["app/new-unclassified-runtime.mjs"], config)
    assert domains == ["shared"] and full, "unknown shared paths must fail safe to the complete suite"
    print(f"CI_DOMAIN_SELECTION_OK tracked={len(tracked)} domains={len(config['domains'])} critical_web_app=full")


if __name__ == "__main__":
    main()
