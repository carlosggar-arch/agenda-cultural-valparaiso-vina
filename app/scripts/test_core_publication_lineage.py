from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from core_publication_lineage import CoreLineageError, canonical_hash, validate


def evidence(root: Path):
    bundle = b'{"release_id":"v250-test"}\n'
    (root / "app/data").mkdir(parents=True)
    (root / "app/data/release-bundle.json").write_bytes(bundle)
    receipt = {
        "contract": "canonical-publication-receipt",
        "publisher": {"run_id": 11, "run_attempt": 1, "source_ref": "a" * 40},
        "finalizer": {"run_id": 22, "run_attempt": 1},
        "public": {"before_sha": "b" * 40, "after_sha": "c" * 40},
        "scope": {"selected_cities": ["gijon"]},
        "preservation": {"gijon": "pass", "valparaiso": "pass"},
        "pre_write_acquisition_fence": {
            "contract": "canonical-publication-acquisition-fence", "core_sha": "a" * 40,
            "intent_id": "d" * 64, "acquisition_shas": {"gijon": "e" * 40},
        },
    }
    receipt_bytes = json.dumps(receipt, sort_keys=True).encode()
    payload = {
        "contract": "core-publication-finalizer-lineage", "version": "1.0.0",
        "core_repository": "carlosggar-arch/agenda-cultural-core",
        "public_repository": "carlosggar-arch/agenda-cultural-valparaiso-vina",
        "core_sha": "a" * 40, "intent_id": "d" * 64,
        "publisher": {"run_id": 11, "run_attempt": 1},
        "finalizer": {"run_id": 22, "run_attempt": 1},
        "public": {"parent_sha": "b" * 40, "sha": "c" * 40},
        "scope": ["gijon"], "acquisition_shas": {"gijon": "e" * 40},
        "release_id": "v250-test", "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "release_bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "preservation": {"gijon": "pass", "valparaiso": "pass"},
        "pre_write_acquisition_fence": receipt["pre_write_acquisition_fence"],
        "canonical_writer": ".github/workflows/finalize-public-agenda.yml",
        "generated_at": "2026-09-08T11:25:32Z",
    }
    payload["attestation_sha256"] = canonical_hash(payload)
    return payload, receipt_bytes


def accepted(root: Path, payload, receipt):
    with patch("core_publication_lineage.subprocess.check_output", side_effect=["b" * 40 + "\n", "1\n"]):
        return validate(attestation_bytes=json.dumps(payload).encode(), receipt_bytes=receipt, repository=root, expected_public_sha="c" * 40)


def test_valid_core_finalizer_lineage_is_accepted(tmp_path: Path):
    payload, receipt = evidence(tmp_path)
    assert accepted(tmp_path, payload, receipt)["intent_id"] == "d" * 64


def test_crossed_tampered_or_replayed_identity_is_rejected(tmp_path: Path):
    payload, receipt = evidence(tmp_path)
    for mutation in ("intent", "publisher", "parent", "bundle", "writer"):
        bad = copy.deepcopy(payload)
        if mutation == "intent": bad["intent_id"] = "f" * 64
        if mutation == "publisher": bad["publisher"]["run_attempt"] = 2
        if mutation == "parent": bad["public"]["parent_sha"] = "f" * 40
        if mutation == "bundle": bad["release_bundle_sha256"] = "f" * 64
        if mutation == "writer": bad["canonical_writer"] = "other.yml"
        bad["attestation_sha256"] = canonical_hash(bad)
        try:
            accepted(tmp_path, bad, receipt)
        except CoreLineageError:
            pass
        else:
            raise AssertionError(f"crossed lineage accepted: {mutation}")


def test_unknown_mode_fields_and_missing_receipt_fail_closed(tmp_path: Path):
    payload, receipt = evidence(tmp_path)
    payload["unknown"] = True
    try:
        accepted(tmp_path, payload, receipt)
    except CoreLineageError:
        pass
    else:
        raise AssertionError("unknown evidence field accepted")
    payload.pop("unknown")
    payload["attestation_sha256"] = canonical_hash(payload)
    try:
        accepted(tmp_path, payload, b"{}")
    except CoreLineageError:
        pass
    else:
        raise AssertionError("missing receipt evidence accepted")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        test_valid_core_finalizer_lineage_is_accepted(root / "one")
        test_crossed_tampered_or_replayed_identity_is_rejected(root / "two")
        test_unknown_mode_fields_and_missing_receipt_fail_closed(root / "three")
    print("CORE_PUBLICATION_LINEAGE_TESTS_OK")
