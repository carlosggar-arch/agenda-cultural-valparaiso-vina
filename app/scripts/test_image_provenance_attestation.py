from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import production_release_attestation as attestation


class ImageProvenanceContract(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="image-provenance-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.addCleanup(patch.stopall)
        patch.object(attestation, "ROOT", self.root).start()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        # Synthetic bytes test provenance, not image decoding (the browser gate
        # remains responsible for decoded pixels). No production evidence is made.
        self.body = b"synthetic-owned-image-fixture"
        self.digest = hashlib.sha256(self.body).hexdigest()
        self.url = f"./assets/event-images/test-city/{self.digest[:24]}.webp"
        self.path = "app/" + self.url[2:]
        self.file = self.root / self.path
        self.file.parent.mkdir(parents=True)
        self.file.write_bytes(self.body)
        self.origin = "https://official.example/exhibit/poster.jpg"
        self.image = {"url": self.url, "origin_url": self.origin, "cache": {
            "source_url": self.origin, "repository_path": self.path,
            "sha256": self.digest, "width": 1600, "height": 1067,
        }}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE).decode().strip()

    def commit(self, image):
        (self.root / "agenda_web.json").write_text(json.dumps({"events": [
            {"id": "unrelated-fixture-id", "title": "Fixture", "image": image}
        ]}), encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "Fixture state")
        return self.git("rev-parse", "HEAD")

    def ready(self, image=None):
        revision = self.commit(self.image if image is None else image)
        self.commit({"url": self.url})
        return revision

    def resolve(self):
        return attestation.image_provenance([{"url": self.url}])

    def test_owned_history_and_repeat_are_byte_identical(self):
        revision = self.ready()
        first = self.resolve()
        self.assertEqual(first[self.url]["origin_url"], self.origin)
        self.assertEqual(first[self.url]["sha256"], self.digest)
        self.assertEqual(first[self.url]["evidence_commit"], revision)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(self.resolve(), sort_keys=True))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_incorrect_attested_hash_is_blocked(self):
        self.image["cache"]["sha256"] = "0" * 64
        self.ready()
        with self.assertRaisesRegex(SystemExit, "Invalid historical"):
            self.resolve()

    def test_missing_file_is_blocked(self):
        self.ready()
        self.file.rename(self.file.with_suffix(".missing"))
        with self.assertRaisesRegex(SystemExit, "missing or unsafe"):
            self.resolve()

    def test_altered_working_bytes_are_blocked(self):
        self.ready()
        self.file.write_bytes(b"altered")
        with self.assertRaisesRegex(SystemExit, "committed bytes"):
            self.resolve()

    def test_historical_blob_must_match_attested_hash(self):
        self.file.write_bytes(b"historical-mismatch")
        self.commit(self.image)
        self.file.write_bytes(self.body)
        self.commit({"url": self.url})
        with self.assertRaisesRegex(SystemExit, "Historical owned image hash mismatch"):
            self.resolve()

    def test_absent_evidence_is_blocked(self):
        self.commit({"url": self.url})
        with self.assertRaisesRegex(SystemExit, "Missing historical"):
            self.resolve()

    def test_conflicting_origin_history_is_ambiguous(self):
        self.commit(self.image)
        changed = copy.deepcopy(self.image)
        changed["origin_url"] = changed["cache"]["source_url"] = "https://other.example/poster.jpg"
        self.ready(changed)
        with self.assertRaisesRegex(SystemExit, "Ambiguous historical"):
            self.resolve()

    def test_exact_origin_correspondence_required(self):
        self.image["cache"]["source_url"] += "?different"
        self.ready()
        with self.assertRaisesRegex(SystemExit, "Invalid historical"):
            self.resolve()

    def test_wrong_attested_path_is_blocked(self):
        self.image["cache"]["repository_path"] = "other.webp"
        self.ready()
        with self.assertRaisesRegex(SystemExit, "Invalid historical"):
            self.resolve()

    def test_path_traversal_is_blocked(self):
        self.ready()
        with self.assertRaisesRegex(SystemExit, "Invalid owned image path"):
            attestation.image_provenance([{"url": "./assets/event-images/../other.webp"}])

    def test_partial_evidence_is_not_ignored(self):
        self.image.pop("cache")
        self.ready()
        with self.assertRaisesRegex(SystemExit, "Invalid historical"):
            self.resolve()

    def test_external_fallback_is_not_claimed_as_owned(self):
        self.commit({"url": self.origin})
        self.assertEqual(attestation.image_provenance([{"url": self.origin}]), {
            self.origin: {"kind": "external", "origin_url": self.origin}
        })
        with patch.object(attestation, "OFFICIAL_IMAGE_EVENT_IDS", ("unrelated-fixture-id",)):
            with self.assertRaisesRegex(SystemExit, "not repository-owned"):
                attestation.official_image_attestation(verify_network=False)

    def test_non_http_fallback_is_blocked(self):
        self.commit({"url": self.origin})
        with self.assertRaises(SystemExit):
            attestation.image_provenance([{"url": "javascript:alert(1)"}])

    def test_shallow_history_cannot_prove_no_ambiguity(self):
        self.ready()
        original = attestation._git_bytes
        def shallow(*args):
            return b"true\n" if args == ("rev-parse", "--is-shallow-repository") else original(*args)
        with patch.object(attestation, "_git_bytes", side_effect=shallow):
            with self.assertRaisesRegex(SystemExit, "complete immutable history"):
                self.resolve()

    def test_unreachable_branch_is_not_durable_publication_evidence(self):
        self.commit({"url": self.url})
        original_branch = self.git("branch", "--show-current")
        self.git("checkout", "-qb", "unpublished-evidence")
        self.commit(self.image)
        self.git("checkout", original_branch)
        with self.assertRaisesRegex(SystemExit, "Missing historical"):
            self.resolve()

    def test_published_origin_bytes_still_must_match_owned_hash(self):
        self.ready()
        with patch.object(attestation, "OFFICIAL_IMAGE_EVENT_IDS", ("unrelated-fixture-id",)):
            with patch.object(attestation, "fetch_bytes", return_value=b"wrong-origin-bytes"):
                with self.assertRaisesRegex(SystemExit, "Official image byte mismatch"):
                    attestation.official_image_attestation(verify_network=True)

    def test_uncommitted_dataset_is_not_attested(self):
        self.ready()
        path = self.root / "agenda_web.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["events"][0]["title"] = "Uncommitted mutation"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "differs from committed publication"):
            attestation.official_image_attestation(verify_network=False)


if __name__ == "__main__":
    unittest.main()
