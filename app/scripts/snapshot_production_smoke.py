"""Run the existing complete production probes against an immutable snapshot.

No deployment, release creation, acquisition or durable write is performed by
this runner. The publish workflow retains the sole certification-history writer.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import subprocess
import sys

import publication_execution_binding as binding
import publication_snapshot_verification as contract
from fast_close_dataset_validation import validate_reference_datasets
from snapshot_verification_cli import (
    GithubReader, require_overlay, require_runtime_composition, require_same_surfaces, write_json,
)


PROBE_GROUPS = {
    "semantics": (("production_admin_staging_smoke.py", "admin-staging.log", ()),
                  ("production_series_contract.py", "series.log", ())),
    "browser-suite": (
        ("production_browser_selenium_smoke.py", "browser.log", ()),
        ("production_warm_start_smoke.py", "warm.log", ()),
        ("test_web_pwa_visibility_parity.py", "parity.log", ("--production",)),
    ),
}


def run(snapshot: Path, evidence: Path, script: str, log: str, arguments=()) -> None:
    with (evidence / log).open("wb") as stream:
        result = subprocess.run([sys.executable, "app/scripts/" + script, *arguments],
                                cwd=snapshot, stdout=stream, stderr=subprocess.STDOUT, check=False)
    print((evidence / log).read_text(encoding="utf-8"), flush=True)
    contract.require(result.returncode == 0, "PROBE_FAILED:" + script)


def run_groups(snapshot: Path, evidence: Path) -> None:
    def group(rows):
        errors = []
        for script, log, arguments in rows:
            if script == "test_web_pwa_visibility_parity.py":
                arguments = (*arguments, "--json-output", str(evidence / "web-pwa-parity.json"))
            try:
                run(snapshot, evidence, script, log, arguments)
            except Exception as exc:
                errors.append(str(exc))
        contract.require(not errors, "PROBE_GROUP_FAILED:" + ";".join(errors))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(group, rows) for rows in PROBE_GROUPS.values()]
        errors = []
        for future in futures:
            try:
                future.result()
            except Exception as exc:
                errors.append(str(exc))
        contract.require(not errors, "PRODUCTION_PROBES_FAILED:" + ";".join(errors))
    contract.require("PRODUCTION_SERIES_CONTRACTS_VERIFIED " in (evidence / "series.log").read_text(),
                     "SERIES_MARKER_MISSING")
    contract.require("PRODUCTION_ADMIN_STAGING_VERIFIED " in (evidence / "admin-staging.log").read_text(),
                     "ADMIN_MARKER_MISSING")
    print("PRODUCTION_PROBES_PARALLEL_OK groups=2 chrome_owners=serialized")


def verify(snapshot: Path, verifier: Path, evidence: Path) -> None:
    validate_reference_datasets(snapshot)
    proof = contract.validate(binding.parse_json((evidence / "snapshot-verification.json").read_bytes()))
    public_sha = proof["original_core_execution"]["binding"]["public_sha"]
    verifier_sha = proof["execution"]["workflow_head_sha"]
    contract.require(proof["execution"] == {"run_id": int(os.environ["GITHUB_RUN_ID"]),
        "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]), "workflow_head_sha": os.environ["GITHUB_SHA"]},
        "EXECUTION_CONTEXT_CHANGED")
    require_overlay(snapshot, verifier, public_sha, verifier_sha)
    require_runtime_composition(verifier, proof, verifier_sha)
    reader = GithubReader(verifier)
    main = reader.api(f"{reader.prefix}/git/ref/heads/main")["object"]["sha"]
    contract.require(main == verifier_sha, "VERIFIER_REF_MOVED")
    cloudflare = reader.api(f"{reader.prefix}/git/ref/heads/cloudflare-preview")["object"]["sha"]
    # The deployed branch may carry verification-only commits, but it must
    # expose the exact same runtime/data surfaces as the independently approved
    # current runtime. This is separate from the historical data composition.
    require_same_surfaces(verifier, verifier_sha, cloudflare)
    raw = evidence / "original/extracted/core-publication-lineage"
    lineage = ("--core-attestation", str(raw / "attestation.json"), "--core-receipt", str(raw / "receipt.json"))
    historical_validation = evidence / "historical-release-validation.json"
    run(snapshot, evidence, "release_finalizer.py", "release-lineage.log",
        ("--check-published", "--finalizer-ref", public_sha, *lineage,
         "--output", str(historical_validation)))
    run(verifier, evidence, "production_pwa_smoke.py", "local-contracts.log", ("local",))
    # One bounded wait, including the corrected consecutive confirmation probe.
    run(verifier, evidence, "deployment_readiness.py", "http.log",
        ("--wait", "--candidate-sha", verifier_sha, "--timeout-seconds", "90", "--poll-seconds", "2",
         "--output", str(evidence / "deployment-readiness.json")))
    run_groups(verifier, evidence)
    shutil.copyfile(evidence / "original/extracted/core-execution.json", evidence / "core-execution.json")
    run(verifier, evidence, "production_release_attestation.py", "attestation.log",
        ("--core-execution-index", str(evidence / "core-execution.json"),
         "--snapshot-verification", str(evidence / "snapshot-verification.json"),
         "--http-log", str(evidence / "http.log"), "--browser-log", str(evidence / "browser.log"),
         "--warm-log", str(evidence / "warm.log"), "--parity-report", str(evidence / "web-pwa-parity.json"),
         "--output", str(evidence / "production-release-attestation.json"),
         "--markdown-output", str(evidence / "summary.md")))
    subprocess.run(["git", "fetch", "origin", "cloudflare-preview"], cwd=verifier, check=True)
    run(verifier, evidence, "production_release_chain.py", "release-chain.log",
        (*lineage, "--cloudflare-ref", "origin/cloudflare-preview",
         "--snapshot-verification", str(evidence / "snapshot-verification.json"),
         "--historical-validation", str(historical_validation),
         "--attestation", str(evidence / "production-release-attestation.json"),
         "--output", str(evidence / "production-release-chain.json")))
    require_overlay(snapshot, verifier, public_sha, verifier_sha)
    current = reader.api(f"{reader.prefix}/git/ref/heads/main")["object"]["sha"]
    contract.require(current == verifier_sha, "VERIFIER_REF_MOVED")
    write_json(evidence / "snapshot-context.json", {"public_sha": public_sha, "verifier_sha": verifier_sha,
        "historical_release_id": proof["composition"]["historical"]["release_id"],
        "runtime_release_id": proof["composition"]["runtime"]["release_id"],
        "publication_created": False, "datasets_changed": False, "historical_success_claimed": False,
        "production_probes": list(PROBE_GROUPS)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--verifier", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    verify(args.snapshot.resolve(), args.verifier.resolve(), args.evidence.resolve())
    print("SNAPSHOT_PRODUCTION_VISUALLY_VERIFIED writes=none")


if __name__ == "__main__":
    main()
