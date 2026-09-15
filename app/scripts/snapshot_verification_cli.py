"""Verify a written snapshot without claiming an intent or deploying a tree."""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

import publication_execution_binding as binding
from publication_execution_github import GithubReader, timestamp
import publication_snapshot_verification as contract
from verify_core_publication_bundle import verify_event, LINEAGE_TRANSPORT


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode())


def local_policy(root: Path, sha: str) -> dict:
    contract.digest(sha, 40, "VERIFIER_SHA")
    return contract.code_policy({
        "tree_sha": git(root, "rev-parse", sha + "^{tree}").decode().strip(),
        "code_hashes": {path: git(root, "rev-parse", f"{sha}:{path}").decode().strip()
                        for path in contract.CODE_PATHS},
    })


def remote_policy(reader: GithubReader, sha: str) -> dict:
    commit = reader.api(f"{reader.prefix}/git/commits/{sha}")
    contract.require(commit.get("sha") == sha, "REMOTE_COMMIT_MISMATCH")
    return contract.code_policy({"tree_sha": commit["tree"]["sha"],
                                 "code_hashes": reader.code_resolver(sha, contract.CODE_PATHS)})


def exact_job(jobs: list, name: str) -> dict:
    found = [job for job in jobs if job.get("name") == name]
    contract.require(len(found) == 1, "JOB_AMBIGUOUS:" + name)
    return found[0]


def checked_endpoint(reader: GithubReader, job: dict) -> str:
    prefix = "https://api.github.com/" + reader.prefix + "/check-runs/"
    url = job.get("check_run_url")
    contract.require(isinstance(url, str) and url.startswith(prefix)
                     and url[len(prefix):].isdigit(), "CHECK_URL_INVALID")
    return url.removeprefix("https://api.github.com/")


def exact_run(reader: GithubReader, run_id: int, attempt: int) -> dict:
    current = reader.api(f"{reader.prefix}/actions/runs/{run_id}")
    contract.require(current.get("id") == run_id and current.get("run_attempt") == attempt,
                     "RUN_ATTEMPT_ADVANCED")
    run = reader.api(f"{reader.prefix}/actions/runs/{run_id}/attempts/{attempt}")
    contract.require(run.get("id") == run_id and run.get("run_attempt") == attempt, "ATTEMPT_MISMATCH")
    contract.require(run.get("status") == "completed", "ORIGINAL_STILL_RUNNING")
    return run


def read_verification(reader: GithubReader, *, root: Path, run: dict, jobs: list) -> dict:
    job = exact_job(jobs, contract.VERIFY_JOB)
    endpoint = checked_endpoint(reader, job)
    annotations = reader.pages(endpoint + "/annotations")
    notices = [row for row in annotations if row.get("title") == contract.NOTICE_TITLE]
    contract.require(len(notices) == 1, "NOTICE_MISSING_OR_AMBIGUOUS")
    proof = contract.decode(notices[0]["message"])
    # This watchdog is executing the independently installed current verifier,
    # not code or an approval document supplied by a downloaded artifact.
    installed_sha = git(root, "rev-parse", "HEAD").decode().strip()
    contract.require(installed_sha == os.environ["GITHUB_SHA"], "WATCHDOG_CHECKOUT_CHANGED")
    contract.verify_github_proof(proof, expected_binding=proof["original_core_execution"]["binding"],
        approved_policy=local_policy(root, installed_sha), actual_policy=remote_policy(reader, run["head_sha"]),
        run=run, job=job, check_run=reader.api(endpoint), annotations=annotations,
        workflow_id=reader.api(f"{reader.prefix}/actions/workflows/publish.yml")["id"])
    contract.require(run.get("status") == "completed" and run.get("conclusion") == "success",
                     "VERIFICATION_NOT_SUCCESSFUL")
    for name in (contract.VERIFY_JOB, contract.SMOKE_JOB):
        item = exact_job(jobs, name)
        contract.require(item.get("conclusion") == "success" and item.get("status") == "completed"
                         and item.get("run_id") == run["id"] and item.get("run_attempt") == run["run_attempt"]
                         and item.get("head_sha") == run["head_sha"], "REQUIRED_JOB_FAILED")
    for name in ("sync-cloudflare", "production-smoke", "refresh-open-release-prs"):
        contract.require(exact_job(jobs, name).get("conclusion") == "skipped", "UNEXPECTED_PUBLICATION_JOB")
    return proof


def download_artifact(reader: GithubReader, *, run: dict, name: str, destination: Path) -> dict:
    rows = reader.pages(f"{reader.prefix}/actions/runs/{run['id']}/artifacts", "artifacts")
    found = [row for row in rows if row.get("name") == name
             and timestamp(row["created_at"]) >= timestamp(run["run_started_at"])
             and timestamp(row["created_at"]) <= timestamp(run["updated_at"])]
    contract.require(len(found) == 1, "ARTIFACT_AMBIGUOUS_OR_MISSING")
    row = found[0]
    contract.require(row.get("expired") is False and type(row.get("id")) is int, "ARTIFACT_EXPIRED")
    workflow_run = row.get("workflow_run") or {}
    contract.require(workflow_run.get("id") == run["id"]
                     and workflow_run.get("head_sha") == run["head_sha"], "ARTIFACT_RUN_MISMATCH")
    declared = row.get("digest", "")
    contract.require(isinstance(declared, str) and declared.startswith("sha256:"), "ARTIFACT_DIGEST_MISSING")
    raw = subprocess.check_output(["gh", "api", f"{reader.prefix}/actions/artifacts/{row['id']}/zip"], timeout=90)
    contract.require("sha256:" + binding.sha256(raw) == declared, "ARTIFACT_DIGEST_MISMATCH")
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "original.zip").write_bytes(raw)
    write_json(destination / "metadata.json", row)
    extract = destination / "extracted"
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        contract.require(len(names) == len(set(names)), "DUPLICATE_ZIP_MEMBER")
        contract.require(len(names) <= 1000 and sum(m.file_size for m in archive.infolist()) <= 100_000_000,
                         "ZIP_TOTAL_TOO_LARGE")
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            contract.require(not path.is_absolute() and ".." not in path.parts
                             and "\\" not in member.filename and ":" not in member.filename
                             and (member.external_attr >> 16) & 0o170000 != 0o120000,
                             "UNSAFE_ZIP_MEMBER")
            contract.require(member.file_size < 25_000_000, "ZIP_MEMBER_TOO_LARGE")
            target = extract.joinpath(*path.parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
    return {"id": row["id"], "sha256": binding.sha256(raw)}


def authenticate_original(reader: GithubReader, *, run: dict, index: dict, expected: dict) -> None:
    contract.require(run["event"] == "repository_dispatch" and run["path"] == binding.WORKFLOW,
                     "ORIGINAL_WORKFLOW_INVALID")
    contract.require(binding.run_key(index["canonical"]) == (run["id"], run["run_attempt"]), "ORIGINAL_OWNER_MISMATCH")
    jobs = reader.pages(f"{reader.prefix}/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs")
    job = exact_job(jobs, "sync-cloudflare")
    endpoint = checked_endpoint(reader, job)
    expected_code = reader.code_hashes(expected["parent_sha"])
    contract.require(reader.code_hashes(expected["public_sha"]) == expected_code, "HISTORICAL_CODE_CHANGED")
    binding.verify_github_index(index, run=run, job=job, check_run=reader.api(endpoint),
                               annotations=reader.pages(endpoint + "/annotations"), expected_binding=expected,
                               workflow_id=reader.api(f"{reader.prefix}/actions/workflows/publish.yml")["id"],
                               expected_code_hashes=expected_code, actual_code_hashes=reader.code_hashes(run["head_sha"]))


def require_same_surfaces(root: Path, public_sha: str, other_sha: str) -> None:
    """Only verification/documentation changes may separate current main/data.

    Every runtime, generated page, image, dataset and release byte is unchanged.
    This is not ancestry-based equivalence or a newly signed publication.
    """
    contract.digest(public_sha, 40, "PUBLIC_SHA")
    contract.digest(other_sha, 40, "OTHER_SHA")
    paths = git(root, "diff", "--name-only", public_sha, other_sha).decode().splitlines()
    allowed = (".github/", "app/scripts/", "docs/", "tests/", "scripts/")
    contract.require(all(path.startswith(allowed) or path in {"AGENTS.md", "requirements-ci.txt"}
                         for path in paths), "PUBLICATION_SURFACES_CHANGED")


def _release_identity(root: Path, sha: str) -> dict:
    bundle = binding.parse_json(git(root, "show", f"{sha}:app/data/release-bundle.json"))
    return {
        "head_sha": sha,
        "release_id": bundle.get("release_id"),
        "tree_sha": git(root, "rev-parse", sha + "^{tree}").decode().strip(),
    }


def build_runtime_composition(root: Path, public_sha: str, runtime_sha: str) -> dict:
    """Bind preserved historical data to a separately verified later runtime.

    This does not claim that the historical release passed production checks.
    It proves instead that every data-bearing surface is byte-identical while
    an exact later runtime, release and whole tree are verified in their own
    right. Unreviewed data, media or generated-content changes fail closed.
    """
    contract.digest(public_sha, 40, "PUBLIC_SHA")
    contract.digest(runtime_sha, 40, "RUNTIME_SHA")
    changed = sorted(git(root, "diff", "--name-only", public_sha, runtime_sha).decode().splitlines())
    contract.require(bool(changed), "COMPOSITION_NOT_DISTINCT")
    preserved = {}
    for path in contract.PRESERVED_SURFACES:
        old = git(root, "rev-parse", f"{public_sha}:{path}").decode().strip()
        new = git(root, "rev-parse", f"{runtime_sha}:{path}").decode().strip()
        contract.require(old == new, "PRESERVED_SURFACE_CHANGED:" + path)
        preserved[path] = old
    contract.require(all(contract.runtime_path(path) for path in changed), "COMPOSITION_PATH_NOT_RUNTIME_ONLY")
    return contract.composition({
        "contract": "historical-data-current-runtime-composition",
        "version": "1.0.0",
        "historical": _release_identity(root, public_sha),
        "runtime": _release_identity(root, runtime_sha),
        "preserved_blobs": preserved,
        "changed_paths": changed,
    })


def require_runtime_composition(root: Path, proof: dict, runtime_sha: str) -> dict:
    value = contract.validate(proof)
    expected = build_runtime_composition(
        root, value["original_core_execution"]["binding"]["public_sha"], runtime_sha)
    contract.require(expected == value["composition"], "COMPOSITION_CHANGED")
    return expected


def require_snapshot_context(snapshot: Path, verifier: Path, public_sha: str, verifier_sha: str) -> None:
    contract.require(git(snapshot, "rev-parse", "HEAD").decode().strip() == public_sha, "SNAPSHOT_HEAD_CHANGED")
    contract.require(git(verifier, "rev-parse", "HEAD").decode().strip() == verifier_sha, "VERIFIER_HEAD_CHANGED")
    # Workflow source must itself still be the reviewed checkout. Its nested
    # data/state checkouts are untracked, so inspect only tracked differences.
    contract.require(not git(verifier, "diff", "HEAD", "--name-only").strip(), "VERIFIER_WORKTREE_CHANGED")
    changed = git(snapshot, "diff", "HEAD", "--name-only").decode().splitlines()
    contract.require(all(path.startswith("app/scripts/") and path.endswith(".py") for path in changed),
                     "SNAPSHOT_NON_VERIFIER_BYTES_CHANGED")
    for path in changed:
        contract.require((snapshot / path).read_bytes() == git(verifier, "show", f"{verifier_sha}:{path}"),
                         "UNAPPROVED_OVERLAY_BYTES")
    approved = approved_scripts(verifier, verifier_sha)
    for file in (snapshot / "app/scripts").rglob("*.py"):
        path = file.relative_to(snapshot).as_posix()
        contract.require(path in approved and not file.is_symlink(), "UNAPPROVED_SCRIPT")
        if not git(snapshot, "ls-files", "--", path).strip():
            contract.require(file.read_bytes() == git(verifier, "show", f"{verifier_sha}:{path}"),
                             "UNAPPROVED_UNTRACKED_SCRIPT")


def approved_scripts(verifier: Path, verifier_sha: str) -> set[str]:
    rows = git(verifier, "ls-tree", "-r", verifier_sha, "--", "app/scripts/").decode().splitlines()
    approved = set()
    for row in rows:
        metadata, path = row.split("\t", 1)
        if path.endswith(".py"):
            contract.require(metadata.startswith(("100644 blob ", "100755 blob ")), "SCRIPT_MODE_INVALID")
            approved.add(path)
    return approved


def require_overlay(snapshot: Path, verifier: Path, public_sha: str, verifier_sha: str) -> None:
    require_snapshot_context(snapshot, verifier, public_sha, verifier_sha)
    for path in approved_scripts(verifier, verifier_sha):
        target = snapshot / path
        contract.require(target.is_file() and not target.is_symlink()
                         and all(not parent.is_symlink() for parent in target.parents)
                         and target.read_bytes() == git(verifier, "show", f"{verifier_sha}:{path}"),
                         "INCOMPLETE_VERIFIER_OVERLAY")


def install_verifier(snapshot: Path, verifier: Path, public_sha: str, verifier_sha: str) -> None:
    require_snapshot_context(snapshot, verifier, public_sha, verifier_sha)
    build_runtime_composition(verifier, public_sha, verifier_sha)
    approved = approved_scripts(verifier, verifier_sha)
    existing = {path.relative_to(snapshot).as_posix() for path in (snapshot / "app/scripts").rglob("*.py")}
    contract.require(existing <= approved, "UNAPPROVED_HISTORICAL_SCRIPT")
    for path in sorted(approved):
        target = snapshot / path
        contract.require(not target.is_symlink()
                         and all(not p.is_symlink() for p in target.parents if p != snapshot.parent),
                         "SYMLINK_OVERLAY_FORBIDDEN")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git(verifier, "show", f"{verifier_sha}:{path}"))
    require_overlay(snapshot, verifier, public_sha, verifier_sha)


def prepare(args, reader: GithubReader) -> dict:
    contract.digest(args.public_sha, 40, "PUBLIC_SHA")
    contract.require(type(args.original_run_id) is int and args.original_run_id > 0
                     and type(args.original_run_attempt) is int and args.original_run_attempt > 0,
                     "ORIGINAL_INPUTS_REQUIRED")
    identity = {"run_id": int(os.environ["GITHUB_RUN_ID"]),
                "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
                "workflow_head_sha": os.environ["GITHUB_SHA"]}
    contract.require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
                     and os.environ.get("GITHUB_REF") == "refs/heads/main"
                     and os.environ.get("GITHUB_REPOSITORY") == binding.WEB_REPOSITORY
                     and identity["run_attempt"] == 1, "NEW_EXPLICIT_EXECUTION_REQUIRED")
    require_snapshot_context(args.snapshot, args.verifier, args.public_sha, identity["workflow_head_sha"])
    current = reader.api(f"{reader.prefix}/git/ref/heads/main")["object"]["sha"]
    contract.require(current == identity["workflow_head_sha"], "VERIFIER_REF_MOVED")
    composed = build_runtime_composition(args.verifier, args.public_sha, current)
    original_run = exact_run(reader, args.original_run_id, args.original_run_attempt)
    artifact = download_artifact(reader, run=original_run,
        name=f"publication-release-decision-{args.original_run_id}-{args.original_run_attempt}",
        destination=args.output / "original")
    source = args.output / "original/extracted"
    index = binding.validate_index(binding.parse_json((source / "core-execution.json").read_bytes()))
    raw_dir = source / "core-publication-lineage"
    lineage, receipt, signed = [(raw_dir / name).read_bytes()
                                for name in ("attestation.json", "receipt.json", "bundle.json")]
    event = {"client_payload": {"public_sha": args.public_sha, "lineage_transport": LINEAGE_TRANSPORT,
        "attestation_base64": base64.b64encode(lineage).decode(), "attestation_sha256": binding.sha256(lineage),
        "receipt_base64": base64.b64encode(receipt).decode(), "sigstore_bundle_base64": base64.b64encode(signed).decode()}}
    # Original signed bytes are transported again; no signature is generated.
    verify_event(event=event, expected_public_sha=args.public_sha, repository=args.snapshot,
                 output_dir=args.output / "lineage")
    expected = binding.binding_from_verified_bytes(lineage=lineage, receipt=receipt, sigstore_bundle=signed,
        release_bundle=(args.snapshot / "app/data/release-bundle.json").read_bytes())
    authenticate_original(reader, run=original_run, index=index, expected=expected)
    exact_run(reader, args.original_run_id, args.original_run_attempt)
    proof = contract.validate({"contract": contract.CONTRACT, "version": contract.VERSION,
        "original_core_execution": index, "execution": identity,
        "verifier": local_policy(args.verifier, identity["workflow_head_sha"]), "original_artifact": artifact,
        "composition": composed},
        expected_binding=expected)
    write_json(args.output / "original-run.json", original_run)
    write_json(args.output / "snapshot-verification.json", proof)
    install_verifier(args.snapshot, args.verifier, args.public_sha, identity["workflow_head_sha"])
    return proof


def verify_watchdog(args, reader: GithubReader) -> dict:
    from production_certification_watchdog import check_certification
    contract.require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_run", "WATCHDOG_AUTOMATIC_EVENT_REQUIRED")
    event = binding.parse_json(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
    event_run = event.get("workflow_run") or {}
    contract.require(event_run.get("id") == args.source_run_id
                     and type(event_run.get("run_attempt")) is int, "WATCHDOG_SOURCE_EVENT_MISMATCH")
    run = exact_run(reader, args.source_run_id, event_run["run_attempt"])
    jobs = reader.pages(f"{reader.prefix}/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs")
    proof = read_verification(reader, root=args.verifier, run=run, jobs=jobs)
    contract.require(event_run.get("head_sha") == run["head_sha"], "WATCHDOG_SOURCE_HEAD_MISMATCH")
    expected = proof["original_core_execution"]["binding"]
    require_runtime_composition(args.verifier, proof, os.environ["GITHUB_SHA"])
    contract.require(git(args.snapshot, "rev-parse", "HEAD").decode().strip() == expected["public_sha"],
                     "SNAPSHOT_HEAD_CHANGED")
    download_artifact(reader, run=run,
        name=f"snapshot-production-verification-{run['id']}-{run['run_attempt']}",
        destination=args.output / "production")
    source = args.output / "production/extracted"
    payload_bytes = (source / "production-release-attestation.json").read_bytes()
    payload = binding.parse_json(payload_bytes)
    contract.require(contract.validate_attestation(payload) == proof, "ATTESTATION_PROOF_MISMATCH")
    # Reverify the original private signature rather than trusting a saved OK.
    raw_dir = source / "original/extracted/core-publication-lineage"
    lineage, receipt, signed = [(raw_dir / name).read_bytes()
                                for name in ("attestation.json", "receipt.json", "bundle.json")]
    old_event = {"client_payload": {"public_sha": expected["public_sha"], "lineage_transport": LINEAGE_TRANSPORT,
        "attestation_base64": base64.b64encode(lineage).decode(), "attestation_sha256": binding.sha256(lineage),
        "receipt_base64": base64.b64encode(receipt).decode(), "sigstore_bundle_base64": base64.b64encode(signed).decode()}}
    verify_event(event=old_event, expected_public_sha=expected["public_sha"], repository=args.snapshot,
                 output_dir=args.output / "reverified-lineage")
    actual = binding.binding_from_verified_bytes(lineage=lineage, receipt=receipt, sigstore_bundle=signed,
        release_bundle=(args.snapshot / "app/data/release-bundle.json").read_bytes())
    contract.require(actual == expected, "HISTORICAL_BINDING_CHANGED")
    old_id, old_attempt = binding.run_key(proof["original_core_execution"]["canonical"])
    old_run = exact_run(reader, old_id, old_attempt)
    artifact = download_artifact(reader, run=old_run,
        name=f"publication-release-decision-{old_id}-{old_attempt}", destination=args.output / "original-check")
    contract.require(artifact == proof["original_artifact"], "HISTORICAL_ARTIFACT_CHANGED")
    authenticate_original(reader, run=old_run, index=proof["original_core_execution"], expected=expected)
    original_dir = args.output / "original-check/extracted"
    contract.require(binding.parse_json((original_dir / "core-execution.json").read_bytes())
                     == proof["original_core_execution"], "ORIGINAL_INDEX_CHANGED")
    for name in ("attestation.json", "receipt.json", "bundle.json"):
        contract.require((original_dir / "core-publication-lineage" / name).read_bytes()
                         == (raw_dir / name).read_bytes(), "ORIGINAL_BYTES_CHANGED")
    retained = check_certification(
        args.state_root, proof["composition"]["runtime"]["head_sha"], payload["release"])
    archive = binding.parse_json((args.state_root / retained["path"]).read_bytes())
    contract.require(contract.validate_attestation(archive) == proof
                     and archive["history_chain"]["attestation_sha256"] == binding.sha256(payload_bytes),
                     "DURABLE_CERTIFICATE_MISMATCH")
    identity = {"run_id": int(os.environ["GITHUB_RUN_ID"]),
        "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]), "workflow_head_sha": os.environ["GITHUB_SHA"]}
    notice = contract.watchdog_notice(proof, execution_identity=identity,
        attestation_sha256=binding.sha256(payload_bytes), archive_sha256=retained["archive_sha256"])
    write_json(args.output / "watchdog.json", notice)
    exact_run(reader, run["id"], run["run_attempt"])
    current = reader.api(f"{reader.prefix}/git/ref/heads/main")["object"]["sha"]
    contract.require(current == identity["workflow_head_sha"], "VERIFIER_REF_MOVED")
    if args.github_output:
        values = {"finalizer_run_id": expected["finalizer"]["run_id"],
                  "finalizer_run_attempt": expected["finalizer"]["run_attempt"],
                  "intent_id": expected["intent_id"], "verification_run_id": run["id"],
                  "verification_run_attempt": run["run_attempt"]}
        with args.github_output.open("a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")
    print(f"::notice file={contract.WATCHDOG_WORKFLOW},line=1,title={contract.WATCHDOG_NOTICE}::{contract.encode_watchdog(notice)}")
    print("SNAPSHOT_CERTIFICATION_WATCHDOG_OK public=" + expected["public_sha"])
    return notice


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "emit", "install", "check-context", "watchdog"))
    parser.add_argument("--snapshot", type=Path, default=Path(".snapshot"))
    parser.add_argument("--verifier", type=Path, default=Path.cwd())
    parser.add_argument("--public-sha")
    parser.add_argument("--original-run-id", type=int)
    parser.add_argument("--original-run-attempt", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, default=Path(".production-certification-state"))
    parser.add_argument("--source-run-id", type=int)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    args.snapshot, args.verifier, args.output = args.snapshot.resolve(), args.verifier.resolve(), args.output.resolve()
    if args.mode == "watchdog":
        verify_watchdog(args, GithubReader(args.verifier))
        return
    if args.mode == "prepare":
        prepare(args, GithubReader(args.verifier))
        print("SNAPSHOT_ORIGINAL_PUBLICATION_AUTHENTICATED")
        return
    proof = contract.validate(binding.parse_json((args.output / "snapshot-verification.json").read_bytes()))
    public = proof["original_core_execution"]["binding"]["public_sha"]
    verifier_sha = proof["execution"]["workflow_head_sha"]
    contract.require(proof["execution"] == {"run_id": int(os.environ["GITHUB_RUN_ID"]),
        "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]), "workflow_head_sha": os.environ["GITHUB_SHA"]},
        "EXECUTION_CONTEXT_CHANGED")
    contract.require(local_policy(args.verifier, verifier_sha) == proof["verifier"], "VERIFIER_POLICY_CHANGED")
    if args.mode == "emit":
        print(f"::notice file={contract.WORKFLOW},line=1,title={contract.NOTICE_TITLE}::{contract.encode(proof)}")
    elif args.mode == "install":
        install_verifier(args.snapshot, args.verifier, public, verifier_sha)
    else:
        require_overlay(args.snapshot, args.verifier, public, verifier_sha)
        current = GithubReader(args.verifier).api("repos/" + binding.WEB_REPOSITORY + "/git/ref/heads/main")["object"]["sha"]
        contract.require(current == verifier_sha, "VERIFIER_REF_MOVED")
        require_runtime_composition(args.verifier, proof, current)
    print("SNAPSHOT_VERIFICATION_CONTEXT_OK public=" + public + " verifier=" + verifier_sha + " writes=none")


if __name__ == "__main__":
    main()
