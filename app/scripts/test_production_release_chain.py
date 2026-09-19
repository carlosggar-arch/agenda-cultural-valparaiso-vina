"""The final chain must retain the already authenticated lineage contract."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import production_release_chain as chain


class ProductionReleaseChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="production-chain-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.visual = self.root / "visual.json"
        self.core = self.root / "original-core-attestation.json"
        self.receipt = self.root / "original-receipt.json"
        self.snapshot = self.root / "snapshot-verification.json"
        self.historical_validation = self.root / "historical-release-validation.json"
        self.published = {
            "base_sha": "a" * 40, "source_sha": "b" * 40,
            "finalizer_sha": "c" * 40, "main_sha": "c" * 40,
            "release": 300, "release_id": "v300-fixture", "source_pr": None,
            "lineage_mode": "CORE_PUBLICATION_FINALIZER",
        }
        self.attestation = {"head_sha": "c" * 40, "release": 300,
                            "release_id": "v300-fixture",
                            "publication_state": "published_and_visually_verified"}
        self.visual.write_text(json.dumps(self.attestation), encoding="utf-8")

    def build(self, **arguments):
        with patch.object(chain, "git", return_value="d" * 40), \
             patch.object(chain, "git_check", return_value=True):
            return chain.build_chain(cloudflare_ref="origin/cloudflare-preview",
                                     attestation_path=self.visual, **arguments)

    def test_core_evidence_reaches_final_published_validation_unchanged(self):
        with patch.object(chain, "check_published", return_value=self.published) as check:
            result = self.build(core_attestation=self.core, core_receipt=self.receipt)
        check.assert_called_once_with("HEAD", core_attestation=self.core, core_receipt=self.receipt)
        self.assertEqual(result["lineage_mode"], "CORE_PUBLICATION_FINALIZER")
        self.assertEqual(result["main_sha"], self.published["main_sha"])
        self.assertEqual(result["publication_state"], "source_to_production_certified")

    def test_pr_web_finalization_keeps_its_own_path(self):
        self.published.update(lineage_mode="PR_WEB_FINALIZATION", source_pr=42)
        with patch.object(chain, "check_published", return_value=self.published) as check:
            result = self.build()
        check.assert_called_once_with("HEAD")
        self.assertEqual(result["lineage_mode"], "PR_WEB_FINALIZATION")
        self.assertEqual(result["source_pr"], 42)

    def test_incomplete_core_evidence_blocks_before_any_fallback(self):
        for arguments in ({"core_attestation": self.core}, {"core_receipt": self.receipt}):
            with self.subTest(arguments=arguments), patch.object(chain, "check_published") as check:
                with self.assertRaisesRegex(SystemExit, "CORE_PUBLICATION_LINEAGE_EVIDENCE_INCOMPLETE"):
                    self.build(**arguments)
                check.assert_not_called()

    def test_crossed_core_receipt_failure_is_not_replaced_by_pr_validation(self):
        with patch.object(chain, "check_published", side_effect=SystemExit("CORE_LINEAGE_RECEIPT_HASH_INVALID")) as check:
            with self.assertRaisesRegex(SystemExit, "CORE_LINEAGE_RECEIPT_HASH_INVALID"):
                self.build(core_attestation=self.core, core_receipt=self.receipt)
        check.assert_called_once_with("HEAD", core_attestation=self.core, core_receipt=self.receipt)

    def test_visual_evidence_for_another_commit_still_blocks(self):
        self.attestation["head_sha"] = "e" * 40
        self.visual.write_text(json.dumps(self.attestation), encoding="utf-8")
        with patch.object(chain, "check_published", return_value=self.published):
            with self.assertRaisesRegex(SystemExit, "RELEASE_CHAIN_ATTESTATION_HEAD_MISMATCH"):
                self.build(core_attestation=self.core, core_receipt=self.receipt)

    def test_snapshot_composition_authenticates_old_lineage_and_current_runtime_separately(self):
        historical = {**self.published, "main_sha": "1" * 40,
                      "release": 251, "release_id": "v251-aaaaaaaaaaaa"}
        proof = {"composition": {
            "historical": {"head_sha": "1" * 40, "release_id": "v251-aaaaaaaaaaaa"},
            "runtime": {"head_sha": "c" * 40, "release_id": "v300-fixture"}}}
        self.snapshot.write_text(json.dumps(proof), encoding="utf-8")
        self.historical_validation.write_text(json.dumps(historical), encoding="utf-8")
        with patch.object(chain.snapshot_contract, "validate", return_value=proof), \
             patch.object(chain.snapshot_contract, "proof_hash", return_value="f" * 64), \
             patch.object(chain, "validate_runtime_release",
                          return_value=(self.published, "c" * 40, [])) as release, \
             patch.object(chain, "check_published", return_value=self.published) as check:
            result = self.build(core_attestation=self.core, core_receipt=self.receipt,
                                snapshot_verification=self.snapshot,
                                historical_validation=self.historical_validation)
        release.assert_called_once_with("c" * 40)
        check.assert_not_called()
        self.assertEqual(result["lineage_mode"], "historical-data-current-runtime-composition")
        self.assertEqual(result["historical_public_sha"], "1" * 40)
        self.assertFalse(result["historical_success_claimed"])
        self.assertEqual(len(result["historical_validation_sha256"]), 64)

    def test_snapshot_composition_rejects_missing_or_crossed_historical_validation(self):
        proof = {"composition": {
            "historical": {"head_sha": "1" * 40, "release_id": "v251-aaaaaaaaaaaa"},
            "runtime": {"head_sha": "c" * 40, "release_id": "v300-fixture"}}}
        self.snapshot.write_text(json.dumps(proof), encoding="utf-8")
        arguments = {"core_attestation": self.core, "core_receipt": self.receipt,
                     "snapshot_verification": self.snapshot}
        with patch.object(chain.snapshot_contract, "validate", return_value=proof):
            with self.assertRaisesRegex(SystemExit, "SNAPSHOT_HISTORICAL_VALIDATION_REQUIRED"):
                self.build(**arguments)
        crossed = {**self.published, "main_sha": "2" * 40,
                   "release_id": "v251-aaaaaaaaaaaa", "lineage_mode": "CORE_PUBLICATION_FINALIZER"}
        self.historical_validation.write_text(json.dumps(crossed), encoding="utf-8")
        with patch.object(chain.snapshot_contract, "validate", return_value=proof):
            with self.assertRaisesRegex(SystemExit, "SNAPSHOT_HISTORICAL_RELEASE_IDENTITY_MISMATCH"):
                self.build(**arguments, historical_validation=self.historical_validation)

    def test_snapshot_allows_only_verified_non_public_cloudflare_difference(self):
        historical = {**self.published, "main_sha": "1" * 40,
                      "release": 251, "release_id": "v251-aaaaaaaaaaaa"}
        proof = {"composition": {
            "historical": {"head_sha": "1" * 40, "release_id": "v251-aaaaaaaaaaaa"},
            "runtime": {"head_sha": "c" * 40, "release_id": "v300-fixture"}}}
        self.snapshot.write_text(json.dumps(proof), encoding="utf-8")
        self.historical_validation.write_text(json.dumps(historical), encoding="utf-8")
        arguments = {"core_attestation": self.core, "core_receipt": self.receipt,
                     "snapshot_verification": self.snapshot,
                     "historical_validation": self.historical_validation}
        with patch.object(chain.snapshot_contract, "validate", return_value=proof), \
             patch.object(chain.snapshot_contract, "proof_hash", return_value="f" * 64), \
             patch.object(chain, "validate_runtime_release",
                          return_value=(self.published, "c" * 40, [])), \
             patch.object(chain, "git", side_effect=["d" * 40, "app/scripts/verifier.py\ndocs/route.md"]), \
             patch.object(chain, "git_check", return_value=False):
            result = chain.build_chain(cloudflare_ref="origin/cloudflare-preview",
                                       attestation_path=self.visual, **arguments)
        self.assertEqual(result["cloudflare_relation"], "verified-non-public-diff")
        self.assertEqual(result["cloudflare_non_public_changed_paths"],
                         ["app/scripts/verifier.py", "docs/route.md"])

        with patch.object(chain.snapshot_contract, "validate", return_value=proof), \
             patch.object(chain, "validate_runtime_release",
                          return_value=(self.published, "c" * 40, [])), \
             patch.object(chain, "git", side_effect=["d" * 40, "agenda_web.json"]), \
             patch.object(chain, "git_check", return_value=False):
            with self.assertRaisesRegex(SystemExit, "RELEASE_CHAIN_CLOUDFLARE_SURFACES_CHANGED"):
                chain.build_chain(cloudflare_ref="origin/cloudflare-preview",
                                  attestation_path=self.visual, **arguments)

    def test_runtime_release_owner_allows_only_later_verification_files(self):
        published = {**self.published, "main_sha": "2" * 40}
        with patch.object(chain, "git", side_effect=["2" * 40, "app/scripts/verifier.py\ndocs/route.md"]), \
             patch.object(chain, "git_check", return_value=True), \
             patch.object(chain, "check_published", return_value=published) as check:
            result, owner, changed = chain.validate_runtime_release("3" * 40)
        check.assert_called_once_with("2" * 40)
        self.assertEqual(result, published)
        self.assertEqual(owner, "2" * 40)
        self.assertEqual(changed, ["app/scripts/verifier.py", "docs/route.md"])

        with patch.object(chain, "git", side_effect=["2" * 40, "agenda_web.json"]), \
             patch.object(chain, "git_check", return_value=True), \
             patch.object(chain, "check_published") as check:
            with self.assertRaisesRegex(SystemExit, "SNAPSHOT_RUNTIME_RELEASE_SURFACES_CHANGED"):
                chain.validate_runtime_release("3" * 40)
        check.assert_not_called()

    def test_cli_preserves_the_explicit_core_paths(self):
        output = self.root / "chain.json"
        result = {**self.published, "cloudflare_sha": "d" * 40,
                  "publication_state": "source_to_production_certified"}
        arguments = ["production_release_chain.py", "--attestation", str(self.visual),
                     "--output", str(output), "--core-attestation", str(self.core),
                     "--core-receipt", str(self.receipt)]
        with patch("sys.argv", arguments), patch.object(chain, "build_chain", return_value=result) as build:
            chain.main()
        build.assert_called_once_with(cloudflare_ref="origin/cloudflare-preview", attestation_path=self.visual,
                                      core_attestation=self.core, core_receipt=self.receipt)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)


if __name__ == "__main__":
    unittest.main()
