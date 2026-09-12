"""Local execution-index/history contracts, not a claim of remote certification.

The upstream verifier authenticates Core's signature and exact input bytes.
These tests exercise retention of that verified index and rejection of altered,
crossed or downgraded metadata. Production-log fixtures are explicitly local;
the existing image/crypto suites own those independent verification boundaries.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import production_release_attestation as attestation
from production_certification_history import (
    CertificationHistoryError,
    persist_certification,
    validate_history,
    validated_core_execution,
)
from publication_execution_binding import WEB_REPOSITORY, build_index
from test_production_release_attestation import fixture_rows


class PublicationExecutionHistoryTests(unittest.TestCase):
    """Reusable from the atomic-publication unittest gate."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="execution-history-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.incoming = self.root / "incoming.json"
        self.binding = {
            "core_sha": "a" * 40,
            "intent_id": "b" * 64,
            "publisher": {"run_id": 101, "run_attempt": 1},
            "finalizer": {"run_id": 102, "run_attempt": 2},
            "public_sha": "c" * 40,
            "parent_sha": "d" * 40,
            "release_id": "v300-111111111111",
            "acquisition_shas": {"valpo": "e" * 40, "gijon": "f" * 40},
            "fence_sha256": "2" * 64,
            "lineage_sha256": "3" * 64,
            "receipt_sha256": "4" * 64,
            "release_bundle_sha256": "5" * 64,
            "sigstore_bundle_sha256": "6" * 64,
        }
        self.index = self.index_for(self.binding)
        self.payload = {
            "schema_version": "1.0.0",
            "verified_at": "2026-09-12T12:00:00Z",
            "head_sha": self.binding["public_sha"],
            "release": 300,
            "release_id": self.binding["release_id"],
            "release_fingerprint": "1" * 64,
            "workflow": {
                "repository": WEB_REPOSITORY,
                "run_id": "201",
                "run_attempt": "3",
                "workflow": "Publish and production verification",
            },
            "publication_state": "published_and_visually_verified",
            "core_execution": self.index,
        }

    @staticmethod
    def index_for(binding: dict) -> dict:
        return build_index(binding=deepcopy(binding), run_id=201, run_attempt=3,
                           workflow_head_sha="7" * 40)

    @staticmethod
    def write_json(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def files_under(path: Path) -> dict[str, bytes]:
        return {item.relative_to(path).as_posix(): item.read_bytes()
                for item in path.rglob("*") if item.is_file()}

    def test_validated_core_execution_preserves_every_binding_field(self):
        original = deepcopy(self.payload)
        self.assertEqual(validated_core_execution(self.payload), self.index)
        self.assertEqual(self.payload, original)
        self.assertEqual(self.index["binding"], self.binding)

    def test_crossed_public_commit_and_release_are_rejected(self):
        for field, value in (("head_sha", "8" * 40), ("release_id", "v300-999999999999")):
            with self.subTest(field=field):
                incoming = deepcopy(self.payload)
                incoming[field] = value
                with self.assertRaisesRegex(CertificationHistoryError, "CORE_PUBLICATION_IDENTITY_MISMATCH"):
                    validated_core_execution(incoming)

    def test_crossed_web_repository_run_and_attempt_are_rejected(self):
        for field, value in (("repository", "another/repository"), ("run_id", "202"),
                             ("run_attempt", "4")):
            with self.subTest(field=field):
                incoming = deepcopy(self.payload)
                incoming["workflow"][field] = value
                with self.assertRaisesRegex(CertificationHistoryError, "CORE_EXECUTION_IDENTITY_MISMATCH"):
                    validated_core_execution(incoming)

    def test_modified_finalizer_attempt_receipt_and_intent_break_the_index_digest(self):
        changes = (
            ("finalizer", {"run_id": 999, "run_attempt": 2}),
            ("finalizer", {"run_id": 102, "run_attempt": 9}),
            ("receipt_sha256", "9" * 64),
            ("intent_id", "8" * 64),
            ("core_sha", "9" * 40),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value):
                incoming = deepcopy(self.payload)
                incoming["core_execution"]["binding"][field] = value
                with self.assertRaisesRegex(CertificationHistoryError, "BINDING_HASH_MISMATCH"):
                    validated_core_execution(incoming)

    def test_incomplete_execution_index_cannot_create_history(self):
        incoming = deepcopy(self.payload)
        del incoming["core_execution"]["binding"]["receipt_sha256"]
        self.write_json(self.incoming, incoming)
        with self.assertRaisesRegex(CertificationHistoryError, "BINDING_FIELDS_INVALID"):
            persist_certification(self.incoming, self.state)
        self.assertEqual(self.files_under(self.state), {})

    def test_delegated_alias_cannot_create_its_own_certification(self):
        incoming = deepcopy(self.payload)
        incoming["core_execution"] = build_index(
            binding=deepcopy(self.binding), run_id=202, run_attempt=1,
            workflow_head_sha="7" * 40, canonical={"run_id": 201, "run_attempt": 3},
        )
        incoming["workflow"].update(run_id="202", run_attempt="1")
        self.write_json(self.incoming, incoming)
        with self.assertRaisesRegex(CertificationHistoryError, "DELEGATED_EXECUTION_CANNOT_CREATE_RECORD"):
            persist_certification(self.incoming, self.state)
        self.assertEqual(self.files_under(self.state), {})

    def test_core_record_reapplication_keeps_archive_and_index_byte_identical(self):
        self.write_json(self.incoming, self.payload)
        archive, index_path, created = persist_certification(self.incoming, self.state)
        self.assertTrue(created)
        archived = json.loads(archive.read_text(encoding="utf-8"))
        self.assertEqual(archived["core_execution"], self.index)
        self.assertEqual(archived["history_chain"]["attestation_sha256"],
                         hashlib.sha256(self.incoming.read_bytes()).hexdigest())
        first = self.files_under(self.state)
        repeat_archive, repeat_index, created_again = persist_certification(self.incoming, self.state)
        self.assertFalse(created_again)
        self.assertEqual((repeat_archive, repeat_index), (archive, index_path))
        self.assertEqual(self.files_under(self.state), first)
        self.assertEqual(validate_history(self.state)["chain"]["length"], 1)

    def test_reindexed_crossed_finalizer_attempt_and_receipt_cannot_replace_existing_record(self):
        self.write_json(self.incoming, self.payload)
        persist_certification(self.incoming, self.state)
        first = self.files_under(self.state)
        for field, value in (("finalizer", {"run_id": 999, "run_attempt": 2}),
                             ("finalizer", {"run_id": 102, "run_attempt": 9}),
                             ("receipt_sha256", "9" * 64)):
            with self.subTest(field=field, value=value):
                changed_binding = deepcopy(self.binding)
                changed_binding[field] = value
                incoming = deepcopy(self.payload)
                incoming["core_execution"] = self.index_for(changed_binding)
                self.write_json(self.incoming, incoming)
                with self.assertRaisesRegex(CertificationHistoryError, "CORE_EXECUTION_CONFLICT_OR_DOWNGRADE"):
                    persist_certification(self.incoming, self.state)
                self.assertEqual(self.files_under(self.state), first)

    def test_core_to_pr_and_pr_to_core_conflicts_leave_existing_history_unchanged(self):
        legacy = deepcopy(self.payload)
        del legacy["core_execution"]
        for direction, first, second in (("core-to-pr", self.payload, legacy),
                                         ("pr-to-core", legacy, self.payload)):
            with self.subTest(direction=direction):
                state = self.root / direction
                self.write_json(self.incoming, first)
                persist_certification(self.incoming, state)
                original = self.files_under(state)
                self.write_json(self.incoming, second)
                with self.assertRaisesRegex(CertificationHistoryError, "CORE_EXECUTION_CONFLICT_OR_DOWNGRADE"):
                    persist_certification(self.incoming, state)
                self.assertEqual(self.files_under(state), original)

    def test_legacy_pr_record_without_core_execution_remains_valid_and_idempotent(self):
        legacy = deepcopy(self.payload)
        del legacy["core_execution"]
        legacy["workflow"] = {"run_id": "300000"}
        legacy["release_id"] = "v300-legacy"
        self.assertIsNone(validated_core_execution(legacy))
        self.write_json(self.incoming, legacy)
        archive, _, created = persist_certification(self.incoming, self.state)
        self.assertTrue(created)
        self.assertNotIn("core_execution", json.loads(archive.read_text(encoding="utf-8")))
        original = self.files_under(self.state)
        self.assertFalse(persist_certification(self.incoming, self.state)[2])
        self.assertEqual(self.files_under(self.state), original)
        self.assertEqual(validate_history(self.state)["latest"]["release_id"], "v300-legacy")

    def test_dropping_archived_core_authority_breaks_the_immutable_archive_hash(self):
        self.write_json(self.incoming, self.payload)
        archive, _, _ = persist_certification(self.incoming, self.state)
        altered = json.loads(archive.read_text(encoding="utf-8"))
        del altered["core_execution"]
        self.write_json(archive, altered)
        with self.assertRaisesRegex(CertificationHistoryError, "ARCHIVE_HASH_MISMATCH"):
            validate_history(self.state)

    @contextmanager
    def local_attestation_inputs(self, *, event: str = "repository_dispatch"):
        """Use real log/parity validators and explicit local identity/image doubles."""
        asset = self.root / "diagnostic-asset.txt"
        asset.write_bytes(b"LOCAL TEST FIXTURE - NOT PUBLICATION EVIDENCE\n")
        image_id = "local-image-fixture"
        official_images = {image_id: {"sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
                                     "visually_verified_surfaces": ["app", "web"]}}
        paths = tuple(self.root / name for name in ("http.log", "browser.log", "warm.log", "parity.json"))
        paths[0].write_text("\n".join(
            f"PRODUCTION_ORIGIN_PARITY_OK origin={origin} release=v300 assets=1\n"
            f"PUBLISHED_PWA_SHELL_OK origin={origin} release=v300" for origin in attestation.ORIGINS
        ), encoding="utf-8")
        markers = [f"PRODUCTION_COLD_LOAD_OK origin={origin} city={city} viewport={viewport} transport=selenium"
                   for origin in attestation.ORIGINS
                   for city, viewport in (("valparaiso", "390x844"), ("gijon", "1280x900"))]
        markers.append("PRODUCTION_CITY_ROUNDTRIP_OK origin=github-pages valparaiso->gijon->valparaiso filter=7-dias transport=selenium")
        markers.extend(f"PRODUCTION_OFFICIAL_IMAGE_OK origin={origin} surface={surface} event={image_id}"
                       for origin in attestation.ORIGINS for surface in ("app", "web"))
        paths[1].write_text("\n".join(markers), encoding="utf-8")
        paths[2].write_text("\n".join(
            f"PRODUCTION_WARM_REOPEN_OK origin={origin} release=v300 viewport=390x844 "
            "cold=1.60s warm=0.80s speedup=2.00x processed_cache=ready" for origin in attestation.ORIGINS
        ), encoding="utf-8")
        self.write_json(paths[3], {"schema_version": "1.0.0", "mode": "production",
                                  "at": "2026-09-12T12:00:00Z", "rows": fixture_rows()})
        environment = {"GITHUB_REPOSITORY": WEB_REPOSITORY, "GITHUB_RUN_ID": "201",
                       "GITHUB_RUN_ATTEMPT": "3", "GITHUB_EVENT_NAME": event,
                       "GITHUB_WORKFLOW": "Publish and production verification"}
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, environment, clear=True))
            stack.enter_context(patch.object(attestation, "ROOT", self.root))
            stack.enter_context(patch.object(attestation, "CRITICAL_ASSETS", [(asset.name, asset.name)]))
            stack.enter_context(patch.object(attestation, "OFFICIAL_IMAGE_EVENT_IDS", (image_id,)))
            stack.enter_context(patch.object(attestation, "release_number", return_value=300))
            stack.enter_context(patch.object(attestation, "release_bundle", return_value={
                "release": 300, "release_id": self.binding["release_id"], "fingerprint": "1" * 64,
            }))
            stack.enter_context(patch.object(attestation, "git_head", return_value=self.binding["public_sha"]))
            image_check = stack.enter_context(patch.object(
                attestation, "official_image_attestation", autospec=True, return_value=official_images))
            stack.enter_context(patch.object(attestation, "fetch_bytes", side_effect=AssertionError("network forbidden")))
            stack.enter_context(patch.object(attestation, "remote_hash_attestation", side_effect=AssertionError("network forbidden")))
            yield paths
            image_check.assert_called_once_with(verify_network=False)

    def test_attestation_builder_preserves_exact_core_execution_index(self):
        self.write_json(self.incoming, self.index)
        with self.local_attestation_inputs() as paths:
            result = attestation.build_attestation(*paths, verify_network=False,
                                                   core_execution_index=self.incoming)
        self.assertEqual(result["core_execution"], self.index)
        self.assertEqual(result["head_sha"], self.binding["public_sha"])
        self.assertFalse(result["critical_assets"]["network_reverified"])

    def test_repository_dispatch_without_execution_index_cannot_attest(self):
        with self.local_attestation_inputs() as paths:
            with self.assertRaisesRegex(SystemExit, "CORE_EXECUTION_EVIDENCE_MISSING"):
                attestation.build_attestation(*paths, verify_network=False)

    def test_pr_push_builder_without_core_execution_keeps_legacy_path(self):
        with self.local_attestation_inputs(event="push") as paths:
            result = attestation.build_attestation(*paths, verify_network=False)
        self.assertNotIn("core_execution", result)

    def test_builder_rejects_index_for_another_public_commit(self):
        changed = deepcopy(self.binding)
        changed["public_sha"] = "8" * 40
        self.write_json(self.incoming, self.index_for(changed))
        with self.local_attestation_inputs() as paths:
            with self.assertRaisesRegex(CertificationHistoryError, "CORE_PUBLICATION_IDENTITY_MISMATCH"):
                attestation.build_attestation(*paths, verify_network=False,
                                              core_execution_index=self.incoming)

    def test_cli_carries_core_execution_index_through_real_builder(self):
        self.write_json(self.incoming, self.index)
        output = self.root / "local-attestation.json"
        with self.local_attestation_inputs() as paths:
            arguments = ["production_release_attestation.py"]
            for flag, path in zip(("--http-log", "--browser-log", "--warm-log", "--parity-report"), paths):
                arguments.extend((flag, str(path)))
            arguments.extend(("--core-execution-index", str(self.incoming), "--output", str(output), "--no-network"))
            with patch("sys.argv", arguments):
                self.assertEqual(attestation.main(), 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["core_execution"], self.index)


if __name__ == "__main__":
    unittest.main()
