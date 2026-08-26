from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PRODUCT_PREFIXES = ("app/", "assets/", "scripts/", "shared/", "tests/", "evento/")
PRODUCT_FILES = {"index.html", "manifest.webmanifest", "agenda_web.json", "fuentes_publicas.json", "sitemap.xml"}
GENERATED_PREFIXES = ("shared/", "scripts/generate_", "scripts/stage31_", "assets/event-", "evento/")
GENERATED_FILES = {"agenda_web.json", "app/data/gijon/agenda_web.json", "sitemap.xml"}
RELEASE_PREFIXES = ("assets/", "shared/", "evento/")


def changed_files(base: str, head: str) -> list[str]:
    if not base:
        # Manual dispatch is an explicit request for the complete validation path.
        return ["app/app.js", "scripts/generate_event_pages.py"]
    output = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base}...{head}"], text=True
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def classify(paths: list[str]) -> dict[str, bool]:
    product = any(path in PRODUCT_FILES or path.startswith(PRODUCT_PREFIXES) for path in paths)
    generated = any(path in GENERATED_FILES or path.startswith(GENERATED_PREFIXES) for path in paths)
    release = any(
        path.startswith(RELEASE_PREFIXES)
        or (path.startswith("app/") and not path.startswith(("app/scripts/", "app/data/quality/")))
        or path in {"index.html", "manifest.webmanifest", "agenda_web.json"}
        for path in paths
    )
    return {"product": product, "generated": generated, "release": release}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--github-output")
    args = parser.parse_args()
    paths = changed_files(args.base, args.head)
    result = classify(paths)
    lines = [f"{key}={'true' if value else 'false'}" for key, value in result.items()]
    lines.append(f"changed_count={len(paths)}")
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print("CI_IMPACT", *lines, sep="\n")


if __name__ == "__main__":
    main()
