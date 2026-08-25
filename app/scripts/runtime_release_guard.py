from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT_INDEX = "index.html"
RELEASE_VERSION = "app/release-version.js"
RUNTIME_PATH = re.compile(
    r"^(?:app/[^/]+\.(?:js|mjs|css|html|webmanifest)|assets/[^/]+\.(?:js|mjs|css)|index\.html|app/cities\.json|manifest\.webmanifest)$"
)
ROOT_JSONLD = re.compile(
    r'(<script id="stage31-root-jsonld" type="application/ld\+json">).*?(</script>)',
    flags=re.S,
)
GENERATED_JSONLD_SENTINEL = "__VIVAMOS_DATA_GENERATED_STAGE31_JSONLD__"


@dataclass(frozen=True)
class ReleaseChangeClassification:
    runtime_changed: tuple[str, ...]
    generated_only: tuple[str, ...]
    release_changed: bool

    @property
    def violation(self) -> bool:
        return bool(self.runtime_changed) and not self.release_changed


def canonicalize_root_index(text: str) -> tuple[str, bool]:
    """Remove only the dataset-owned Stage 3.1 JSON-LD payload from comparison.

    The surrounding tag, all other HTML, inline scripts, stylesheets and shell
    markup remain byte-significant. If the owned marker disappears, appears, or
    changes structurally, that remains a runtime change and still requires a
    release bump.
    """

    matches = list(ROOT_JSONLD.finditer(text))
    if len(matches) != 1:
        return text, False
    normalized = ROOT_JSONLD.sub(
        rf"\1{GENERATED_JSONLD_SENTINEL}\2",
        text,
        count=1,
    )
    return normalized, True


def root_index_runtime_changed(before: str, after: str) -> bool:
    before_normalized, before_owned = canonicalize_root_index(before)
    after_normalized, after_owned = canonicalize_root_index(after)
    if before_owned != after_owned:
        return True
    return before_normalized != after_normalized


def classify_release_change(
    changed_paths: Iterable[str],
    *,
    before_index: str | None = None,
    after_index: str | None = None,
) -> ReleaseChangeClassification:
    changed = tuple(dict.fromkeys(str(path).strip() for path in changed_paths if str(path).strip()))
    runtime: list[str] = []
    generated_only: list[str] = []

    for path in changed:
        if path == ROOT_INDEX:
            if before_index is None or after_index is None or root_index_runtime_changed(before_index, after_index):
                runtime.append(path)
            else:
                generated_only.append(path)
            continue
        if RUNTIME_PATH.fullmatch(path):
            runtime.append(path)

    return ReleaseChangeClassification(
        runtime_changed=tuple(runtime),
        generated_only=tuple(generated_only),
        release_changed=RELEASE_VERSION in changed,
    )


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip()


def _git_show_optional(ref: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def evaluate_git_range(base_ref: str, head_ref: str) -> ReleaseChangeClassification:
    changed = _git("diff", "--name-only", base_ref, head_ref).splitlines()
    before_index = after_index = None
    if ROOT_INDEX in changed:
        before_index = _git_show_optional(base_ref, ROOT_INDEX)
        after_index = _git_show_optional(head_ref, ROOT_INDEX)
    return classify_release_change(
        changed,
        before_index=before_index,
        after_index=after_index,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Require a PWA release bump for executable/runtime changes while allowing explicitly marked data-generated SEO payloads."
    )
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    args = parser.parse_args()

    classification = evaluate_git_range(args.base_ref, args.head_ref)
    generated = ",".join(classification.generated_only) or "none"
    runtime = ",".join(classification.runtime_changed) or "none"

    if classification.violation:
        print("Production-visible PWA runtime changed without bumping app/release-version.js:")
        for path in classification.runtime_changed:
            print(path)
        print("A canonical finalizer release is required before production verification.")
        print(
            "RELEASE_RUNTIME_GUARD_BLOCKED "
            f"runtime={runtime} generated_only={generated} release_changed=false"
        )
        return 1

    print(
        "RELEASE_RUNTIME_GUARD_OK "
        f"runtime={runtime} generated_only={generated} "
        f"release_changed={str(classification.release_changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
