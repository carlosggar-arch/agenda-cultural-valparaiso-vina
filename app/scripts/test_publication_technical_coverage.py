"""Transport/compatibility tests; Core owns per-unit failure authorization."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import core_publication_lineage as lineage
import production_certification_history as history
import production_release_attestation as production
import release_bundle
from production_release_chain import validate_visual_attestation
from test_core_publication_lineage import evidence


class TechnicalCoverageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def fixture(self, *, state="pending", city="gijon"):
        payload, receipt_bytes = evidence(self.root)
        units = [] if state is None else [{"unit_id": "unit_" + "1" * 24, "state": state}]
        manifest = {"contract": "publication-technical-pending/1", "schema_version": "1.0.0", "city": city, "units": units}
        raw = (json.dumps(manifest) + "\n").encode()
        path = self.root / lineage.PENDING_PATHS[city]
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
        bundle = {"release_id": "v250-test", "components": {f"technical_pending_{city}": {
            "path": lineage.PENDING_PATHS[city], "sha": release_bundle.git_blob_sha(path)}}}
        bundle_bytes = json.dumps(bundle).encode()
        (self.root / "app/data/release-bundle.json").write_bytes(bundle_bytes)
        coverage = {"contract": "publication-coverage/1", "status": "technical_pending" if state == "pending" else "complete",
                    "pending_units": int(state == "pending"), "manifests": {city: hashlib.sha256(raw).hexdigest()}}
        receipt = json.loads(receipt_bytes)
        receipt["coverage"] = coverage
        receipt_bytes = json.dumps(receipt).encode()
        payload.update(version="1.1.0", coverage=copy.deepcopy(coverage),
                       receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
                       release_bundle_sha256=hashlib.sha256(bundle_bytes).hexdigest())
        payload["attestation_sha256"] = lineage.canonical_hash(payload)
        return payload, receipt_bytes, path, bundle

    def accept(self, payload, receipt_bytes, *, previous=None, committed=None):
        def git(command, **kwargs):
            if command[1] == "rev-parse": return "b" * 40 + "\n"
            if command[1] == "rev-list": return "1\n"
            if command[1] == "ls-tree":
                exists = (self.root / command[-1]).exists() if previous is None else bool(previous)
                return f"100644 blob {'0' * 40}\t{command[-1]}\n" if exists else ""
            revision, relative = command[2].split(":", 1)
            if revision == "b" * 40 and previous is not None: return previous
            if revision == "c" * 40 and committed is not None: return committed
            return (self.root / relative).read_bytes()
        with patch.object(lineage.subprocess, "check_output", side_effect=git):
            return lineage.validate(attestation_bytes=json.dumps(payload).encode(), receipt_bytes=receipt_bytes,
                                    repository=self.root, expected_public_sha="c" * 40)

    def test_pending_lineage_and_complete_resolved_manifest(self):
        payload, receipt, _path, _bundle = self.fixture()
        self.assertEqual(self.accept(payload, receipt)["coverage"], payload["coverage"])
        self.assertEqual(payload["version"], "1.1.0")

    def test_empty_resolved_manifest_remains_component(self):
        payload, receipt, path, bundle = self.fixture(state=None)
        self.assertEqual(self.accept(payload, receipt)["coverage"]["status"], "complete")
        self.assertIn("technical_pending_gijon", bundle["components"])
        self.assertTrue(path.is_file())

    def test_resolved_units_do_not_count_as_pending(self):
        payload, receipt, _path, _bundle = self.fixture(state="resolved")
        self.assertEqual(self.accept(payload, receipt)["coverage"]["pending_units"], 0)

    def test_receipt_or_lineage_cannot_drop_or_cross_coverage(self):
        payload, receipt, _path, _bundle = self.fixture()
        for mutation in ("receipt_absent", "receipt_null", "receipt_count", "payload_absent", "version_downgrade", "payload_extra"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(payload)
                receipt_value = json.loads(receipt)
                if mutation == "receipt_absent": receipt_value.pop("coverage")
                elif mutation == "receipt_null": receipt_value["coverage"] = None
                elif mutation == "receipt_count": receipt_value["coverage"]["pending_units"] = 2
                elif mutation == "payload_absent": changed.pop("coverage")
                elif mutation == "version_downgrade": changed["version"] = "1.0.0"
                else: changed["coverage"]["extra"] = True
                raw = json.dumps(receipt_value).encode()
                changed["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
                changed["attestation_sha256"] = lineage.canonical_hash(changed)
                with self.assertRaises(lineage.CoreLineageError): self.accept(changed, raw)

    def test_component_or_file_cannot_be_dropped_or_rebound(self):
        payload, receipt, path, bundle = self.fixture()
        original = path.read_bytes()
        for mutation in ("component_absent", "component_extra", "component_hash", "component_path", "file_absent", "file_changed"):
            with self.subTest(mutation=mutation):
                packaged = copy.deepcopy(bundle)
                path.write_bytes(original)
                if mutation == "component_absent": packaged["components"] = {}
                elif mutation == "component_extra": packaged["components"]["technical_pending_other"] = {}
                elif mutation == "component_hash": packaged["components"]["technical_pending_gijon"]["sha"] = "0" * 40
                elif mutation == "component_path": packaged["components"]["technical_pending_gijon"]["path"] = "other.json"
                elif mutation == "file_absent": path.unlink()
                else: path.write_bytes(b"{}")
                bundle_bytes = json.dumps(packaged).encode()
                (self.root / "app/data/release-bundle.json").write_bytes(bundle_bytes)
                changed = copy.deepcopy(payload)
                changed["release_bundle_sha256"] = hashlib.sha256(bundle_bytes).hexdigest()
                changed["attestation_sha256"] = lineage.canonical_hash(changed)
                with self.assertRaises(lineage.CoreLineageError): self.accept(changed, receipt)

    def test_uncommitted_or_unselected_manifest_mutation_is_rejected(self):
        payload, receipt, path, _bundle = self.fixture(city="valpo")
        self.assertEqual(self.accept(payload, receipt)["scope"], ["gijon"])
        with self.assertRaisesRegex(lineage.CoreLineageError, "UNSELECTED_CHANGED"):
            self.accept(payload, receipt, previous=b"different prior bytes")
        with self.assertRaisesRegex(lineage.CoreLineageError, "NOT_COMMITTED"):
            self.accept(payload, receipt, committed=b"different committed bytes")
        with self.assertRaisesRegex(lineage.CoreLineageError, "UNSELECTED_CHANGED"):
            self.accept(payload, receipt, previous=b"")

    def test_unselected_manifest_cannot_disappear_from_snapshot(self):
        payload, _receipt, _path, _bundle = self.fixture(city="valpo")
        def git(command, **kwargs):
            if command[1] == "show": return (self.root / command[2].split(":", 1)[1]).read_bytes()
            return f"100644 blob {'0' * 40}\t{command[-1]}\n"
        with patch.object(lineage.subprocess, "check_output", side_effect=git):
            with self.assertRaisesRegex(lineage.CoreLineageError, "UNSELECTED_CHANGED"):
                lineage._committed_coverage(self.root, "c" * 40, "b" * 40, ["valpo"], payload["coverage"])

    def test_declared_status_and_count_are_not_free_claims(self):
        payload, receipt, path, bundle = self.fixture()
        for change in ("status", "count", "bool_count", "hash", "city"):
            coverage = copy.deepcopy(payload["coverage"])
            if change == "status": coverage["status"] = "complete"
            elif change == "count": coverage["pending_units"] = 2
            elif change == "bool_count": coverage["pending_units"] = True
            elif change == "hash": coverage["manifests"]["gijon"] = "wrong"
            else: coverage["manifests"] = {"other": "a" * 64}
            altered = copy.deepcopy(payload)
            altered["coverage"] = coverage
            receipt_value = json.loads(receipt)
            receipt_value["coverage"] = coverage
            raw = json.dumps(receipt_value).encode()
            altered["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
            altered["attestation_sha256"] = lineage.canonical_hash(altered)
            with self.subTest(change=change), self.assertRaises(lineage.CoreLineageError): self.accept(altered, raw)

    def test_bundle_adds_optional_components_without_changing_legacy_case(self):
        with patch.object(release_bundle, "ROOT", self.root), patch.object(release_bundle, "COMPONENTS", {}), patch.object(release_bundle, "release_number", return_value=1):
            legacy = release_bundle.build_release_bundle()
            self.assertEqual(legacy["components"], {})
            path = self.root / lineage.PENDING_PATHS["valpo"]
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"contract": "publication-technical-pending/1", "schema_version": "1.0.0", "city": "valpo", "units": []}))
            current = release_bundle.build_release_bundle()
            self.assertNotEqual(legacy["release_id"], current["release_id"])
            self.assertEqual(set(current["components"]), {"technical_pending_valpo"})

    def test_capability_is_explicit_and_legacy_consumer_remains_unsupported(self):
        capability = json.loads((Path(__file__).resolve().parents[1] / "publication-capabilities.json").read_text())
        self.assertEqual(capability["contract"], "publication-consumer-capabilities/1")
        self.assertIn("publication-technical-pending/1", capability["supports"])

    def test_production_attestation_binds_delivered_coverage_without_full_coverage_claim(self):
        payload, _receipt, path, bundle = self.fixture()
        raw = path.read_bytes()
        with patch.object(production, "ROOT", self.root), patch.object(production, "_git_bytes", return_value=raw), patch.object(production, "fetch_bytes", return_value=raw):
            result = production.technical_coverage_attestation(bundle, verify_network=True)
            self.assertEqual(result["coverage"], payload["coverage"])
            self.assertEqual(set(result["coverage_delivery"]["origins_sha256"]), set(production.ORIGINS))
            with patch.object(production, "fetch_bytes", return_value=b"wrong"):
                with self.assertRaisesRegex(SystemExit, "COVERAGE_BYTE_MISMATCH"):
                    production.technical_coverage_attestation(bundle, verify_network=True)

    def test_chain_and_durable_history_preserve_pending_and_reject_downgrade(self):
        payload, _receipt, _path, _bundle = self.fixture()
        attestation = {"release": 250, "release_id": "v250-test", "release_fingerprint": "fingerprint",
                       "head_sha": "c" * 40, "publication_state": "published_and_visually_verified", "coverage": payload["coverage"]}
        published = {"release": 250, "release_id": "v250-test", "main_sha": "c" * 40, "coverage": payload["coverage"]}
        validate_visual_attestation(attestation, published)
        with self.assertRaisesRegex(SystemExit, "COVERAGE_MISMATCH"):
            validate_visual_attestation({key: value for key, value in attestation.items() if key != "coverage"}, published)
        path = self.root / "production.json"
        path.write_text(json.dumps(attestation))
        state = self.root / "state"
        archive, index, created = history.persist_certification(path, state)
        self.assertTrue(created)
        archived_bytes = archive.read_bytes()
        self.assertEqual(history.validate_history(state)["latest"]["coverage"], payload["coverage"])
        self.assertFalse(history.persist_certification(path, state)[2])
        self.assertEqual(archive.read_bytes(), archived_bytes)
        attestation.pop("coverage")
        path.write_text(json.dumps(attestation))
        with self.assertRaisesRegex(history.CertificationHistoryError, "IMMUTABLE_PATH_CONFLICT"):
            history.persist_certification(path, state)
        altered = json.loads(index.read_text())
        altered["certifications"][0].pop("coverage")
        index.write_text(json.dumps(altered))
        with self.assertRaisesRegex(history.CertificationHistoryError, "COVERAGE_CONFLICT"):
            history.validate_history(state)


if __name__ == "__main__":
    unittest.main()
