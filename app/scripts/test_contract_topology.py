from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "tests" / "contract-topology.json"
RUNNER = ROOT / "app" / "scripts" / "run_contracts.py"
BROWSER_RUNNER = ROOT / "app" / "scripts" / "run_browser_scenarios.py"
REQUIRED_WORKFLOW = ROOT / ".github" / "workflows" / "required-release-guard.yml"
TEMPORAL_WORKFLOW = ROOT / ".github" / "workflows" / "temporal-priority-validation.yml"
PRODUCTION_WORKFLOW = ROOT / ".github" / "workflows" / "production-pwa-smoke.yml"

ALLOWED_LAYERS = {"semantic", "architecture", "browser", "release"}
REQUIRED_BROWSER_WORKFLOW = ".github/workflows/required-release-guard.yml"


def fail(message: str) -> None:
    raise AssertionError(message)


def require_path(relative: str, *, label: str) -> None:
    path = ROOT / relative
    if not path.is_file():
        fail(f"{label} does not exist: {relative}")


def main() -> None:
    data = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.4.0":
        fail("contract topology schema_version must be 1.4.0 for the general change guard")
    if not RUNNER.is_file():
        fail("canonical contract runner is missing")
    if not BROWSER_RUNNER.is_file():
        fail("canonical browser scenario runner is missing")

    runner_source = RUNNER.read_text(encoding="utf-8")
    if 'entry.get("runner_args", [])' not in runner_source:
        fail("canonical contract runner must honor declarative runner_args")

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
    known_ids = set(ids)

    domains_by_layer: dict[str, set[str]] = defaultdict(set)
    contracts_by_id = {entry["id"]: entry for entry in contracts}
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
        runner_args = entry.get("runner_args", [])
        if not isinstance(runner_args, list) or any(not isinstance(value, str) for value in runner_args):
            fail(f"{contract_id}: runner_args must be a list of strings")
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

    profiles = data.get("runner_profiles")
    if not isinstance(profiles, dict) or not profiles:
        fail("runner_profiles must be a non-empty object")
    for profile, profile_ids in profiles.items():
        if not isinstance(profile, str) or not profile.strip():
            fail("runner profile names must be non-empty")
        if not isinstance(profile_ids, list) or not profile_ids:
            fail(f"runner profile {profile} must contain contracts")
        if len(profile_ids) != len(set(profile_ids)):
            fail(f"runner profile {profile} contains duplicate contracts")
        for contract_id in profile_ids:
            if contract_id not in known_ids:
                fail(f"runner profile {profile} references unknown contract: {contract_id}")
            owner = contracts_by_id[contract_id]["owner"]
            if not owner.endswith((".py", ".mjs", ".js")):
                fail(f"runner profile {profile} contains workflow-only contract: {contract_id}")

    if profiles.get("temporal-fast") != ["semantic.temporal-priority", "semantic.agenda-order"]:
        fail("temporal-fast must contain only the two canonical semantic ordering contracts")
    for required_id in (
        "release.generated-shell",
        "architecture.startup",
        "architecture.public-presentation",
        "release.local-pwa-smoke",
        "release.production-smoke-contract",
    ):
        if required_id not in profiles.get("required-release", []):
            fail(f"required-release profile missing D4 contract: {required_id}")

    scenarios = data.get("browser_scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        fail("browser_scenarios must be a non-empty object")
    seen_browser_contracts: set[str] = set()
    for scenario, scenario_ids in scenarios.items():
        if not isinstance(scenario, str) or not scenario.strip():
            fail("browser scenario names must be non-empty")
        if not isinstance(scenario_ids, list) or not scenario_ids:
            fail(f"browser scenario {scenario} must contain contracts")
        if len(scenario_ids) != len(set(scenario_ids)):
            fail(f"browser scenario {scenario} contains duplicate contracts")
        for contract_id in scenario_ids:
            if contract_id not in known_ids:
                fail(f"browser scenario {scenario} references unknown contract: {contract_id}")
            entry = contracts_by_id[contract_id]
            if entry["layer"] != "browser":
                fail(f"browser scenario {scenario} contains non-browser contract: {contract_id}")
            if not entry["owner"].endswith(".py"):
                fail(f"browser scenario {scenario} owner must be Python executable: {contract_id}")
            if entry.get("workflow") != REQUIRED_BROWSER_WORKFLOW:
                fail(f"browser contract must be composed by Required release guard after D4: {contract_id}")
            if contract_id in seen_browser_contracts:
                fail(f"browser contract belongs to more than one canonical scenario: {contract_id}")
            seen_browser_contracts.add(contract_id)

    all_browser_contracts = {entry["id"] for entry in contracts if entry["layer"] == "browser"}
    if seen_browser_contracts != all_browser_contracts:
        missing = sorted(all_browser_contracts - seen_browser_contracts)
        extra = sorted(seen_browser_contracts - all_browser_contracts)
        fail(f"every browser contract must belong to exactly one scenario; missing={missing} extra={extra}")
    if scenarios.get("computed-presentation") != ["browser.computed-ui-contracts"]:
        fail("computed UI contracts must be a canonical required browser scenario")
    if scenarios.get("temporal-order") != ["browser.temporal-priority"]:
        fail("temporal priority browser owner must be centralized in the temporal-order scenario")

    overlaps = data.get("temporary_overlaps")
    if overlaps != []:
        fail("D4 final topology must contain no temporary overlaps")

    required = REQUIRED_WORKFLOW.read_text(encoding="utf-8")
    temporal = TEMPORAL_WORKFLOW.read_text(encoding="utf-8")
    production = PRODUCTION_WORKFLOW.read_text(encoding="utf-8")
    if "python app/scripts/run_browser_scenarios.py --all" not in required:
        fail("Required release guard must be the single browser scenario composer")
    if "_browser.py" in temporal:
        fail("fast temporal workflow must not execute browser owners after D4")
    if "python app/scripts/run_contracts.py --profile temporal-fast" not in temporal:
        fail("fast temporal workflow must invoke the canonical temporal-fast profile")
    production_triggers = production.split("permissions:", 1)[0]
    if "pull_request:" in production_triggers:
        fail("Production PWA smoke must not run as a PR workflow after D4")
    if "push:" not in production_triggers or "branches: [main]" not in production_triggers:
        fail("Production PWA smoke must remain post-merge on main")

    print(
        "CONTRACT_TOPOLOGY_OK "
        f"contracts={len(contracts)} "
        f"profiles={len(profiles)} "
        f"browser_scenarios={len(scenarios)} "
        f"browser_contracts={len(all_browser_contracts)} "
        f"stage_c_domains={len(stage_c_domains)} "
        "temporary_overlaps=0 final_stage_d=true"
    )


if __name__ == "__main__":
    main()
