from __future__ import annotations

from pathlib import Path
import unittest

from test_verify_core_publication_bundle import BundleConsumerTests
from test_production_release_chain import ProductionReleaseChainTests
from test_publication_execution_github import PublicationExecutionGithubTests
from test_publication_execution_history import PublicationExecutionHistoryTests
from test_publication_execution_routing import PublicationExecutionRoutingTests

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
PUBLISH = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
PR_FAST = (WORKFLOWS / "pr-fast.yml").read_text(encoding="utf-8")
PR_RELEASE = (WORKFLOWS / "pr-release.yml").read_text(encoding="utf-8")
FINALIZER_MARKER = "agenda-cultural-core/.github/workflows/finalize-public-agenda.yml"


def pushes_public_main(text: str) -> bool:
    compact = text.replace("'", "").replace('"', "")
    return any(marker in compact for marker in (
        "git push origin HEAD:main", "git push origin main",
        "git push --force origin HEAD:main", "git push --force-with-lease origin HEAD:main",
    ))


def main() -> None:
    offenders = [
        path.name for path in WORKFLOWS.glob("*.yml")
        if pushes_public_main(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, "PUBLIC_DATASET_SECONDARY_MAIN_WRITERS: " + ", ".join(offenders)
    assert "push:" not in PR_FAST.split("permissions:", 1)[0]
    assert "push:" not in PR_RELEASE.split("permissions:", 1)[0]
    triggers = PUBLISH.split("permissions:", 1)[0]
    assert "push:" in triggers and "branches: [main]" in triggers
    assert "pull_request:" not in triggers
    assert "contents: read" in PUBLISH
    assert "git push origin HEAD:main" not in PUBLISH
    assert "test_web_pwa_visibility_parity.py" in PUBLISH
    assert "production_release_attestation.py" in PUBLISH
    # This owner runs even for no-release changes to publication machinery.
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case)
                               for case in (BundleConsumerTests, ProductionReleaseChainTests,
                                            PublicationExecutionGithubTests, PublicationExecutionHistoryTests,
                                            PublicationExecutionRoutingTests))
    result = unittest.TextTestRunner().run(suite)
    assert result.wasSuccessful(), "Core publication bundle consumer contract failed"
    print(
        "ATOMIC_PUBLICATION_CONTRACT_OK "
        f"protected_writer={FINALIZER_MARKER} secondary_public_main_writers=0"
    )


if __name__ == "__main__":
    main()
