from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "tests" / "contract-topology.json"

ALLOWED_LAYERS = {"semantic", "architecture", "browser", "release"}
ALLOWED_FOLLOWUPS = {"D2", "D3", "D4"}


def fail(message: str) -> None:
    raise AssertionError(message)


def require_path(relative: str, *, label: str) -> None:
    path = ROOT / relative
    if not path.is_file():
        fail(f"{label} does not exist: {relative}")


def main() -> None:
    data = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0.0":
        fail("contract topology schema_version must be 1.0.0")

    declared_layers = data.get("layers")
    if set(declared_layers or []) != ALLOWED_LAYERS or len(declared_layers) != len(ALLOWED_LAYERS):
        fail(f"layers must be exactly {sorted(ALLOWED_LAYERS)}")

    contracts = data.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        fail("contracts must be a non-empty list")

    ids = [entry.get("id") for entry in contracts]
    duplicate_ids = sorted(key for key, count in Counter(ids).items() if key and count > 1)
    if duplicate_ids:
        fail(f"contract ids must be unique: {duplicate_ids}")
    if any(not isinstance(contract_id, str) or not contract_id.strip() for contract_id in ids):
        fail("every contract needs a non-empty id")

    domains_by_layer: dict[str, set[str]] = defaultdict(set)
    for entry in contracts:
        contract_id = entry["id"]
        layer = entry.get("layer")
        domain = entry.get("domain")
        owner = entry.get("owner")
        workflow = entry.get("workflow")

        if layer not in ALLOWED_LAYERS:
            fail(f"{contract_id}: invalid layer {layer!r}")
        if not isinstance(domain, str) or not domain.strip():
            fail(f"{contract_id}: domain is required")
        if not isinstance(owner, str) or not owner.strip():
            fail(f"{contract_id}: owner is required")
        require_path(owner, label=f"{contract_id} owner")
        if workflow is not None:
            if not isinstance(workflow, str) or not workflow.startswith(".github/workflows/"):
                fail(f"{contract_id}: workflow must live under .github/workflows")
            require_path(workflow, label=f"{contract_id} workflow")
        domains_by_layer[layer].add(domain)

    stage_c_domains = data.get("stage_c_domains")
    if not isinstance(stage_c_domains, list) or not stage_c_domains:
        fail("stage_c_domains must be a non-empty list")
    if len(stage_c_domains) != len(set(stage_c_domains)):
        fail("stage_c_domains must be unique")

    protected_domains = domains_by_layer["semantic"] | domains_by_layer["architecture"]
    missing_stage_c = sorted(set(stage_c_domains) - protected_domains)
    if missing_stage_c:
        fail(f"Stage C authority domains missing canonical semantic/architecture owners: {missing_stage_c}")

    overlaps = data.get("temporary_overlaps")
    if not isinstance(overlaps, list):
        fail("temporary_overlaps must be a list")
    overlap_keys: set[tuple[str, str]] = set()
    for overlap in overlaps:
        contract = overlap.get("contract")
        owner_workflow = overlap.get("owner_workflow")
        duplicate_workflow = overlap.get("duplicate_workflow")
        remove_in = overlap.get("remove_in")
        reason = overlap.get("reason")
        if not all(isinstance(value, str) and value.strip() for value in (contract, owner_workflow, duplicate_workflow, reason)):
            fail("temporary overlaps need contract, owner_workflow, duplicate_workflow and reason")
        if owner_workflow == duplicate_workflow:
            fail(f"{contract}: overlap must name two different workflows")
        require_path(owner_workflow, label=f"{contract} owner workflow")
        require_path(duplicate_workflow, label=f"{contract} duplicate workflow")
        if remove_in not in ALLOWED_FOLLOWUPS:
            fail(f"{contract}: remove_in must be one of {sorted(ALLOWED_FOLLOWUPS)}")
        key = (contract, duplicate_workflow)
        if key in overlap_keys:
            fail(f"duplicate overlap declaration: {key}")
        overlap_keys.add(key)

    print(
        "CONTRACT_TOPOLOGY_OK "
        f"contracts={len(contracts)} "
        f"stage_c_domains={len(stage_c_domains)} "
        f"temporary_overlaps={len(overlaps)}"
    )


if __name__ == "__main__":
    main()
