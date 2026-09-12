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
