from __future__ import annotations

import argparse
import subprocess
import sys


SOURCE_SUITES = {
    "balmaceda": [
        "app/scripts/test_balmaceda_valpo.py",
        "app/scripts/test_balmaceda_transport.py",
        "app/scripts/test_balmaceda_coverage.py",
    ],
    "museo_maritimo": ["app/scripts/test_museo_maritimo.py"],
    "visitavina_fonck": ["app/scripts/test_visitavina_fonck.py", "app/scripts/test_fonck_coverage.py"],
    "visitavina_estadio": [
        "app/scripts/test_visitavina_estadio_espanol.py",
        "app/scripts/test_estadio_espanol_coverage.py",
    ],
    "registry": ["app/scripts/test_source_registry.py", "app/scripts/validate_source_registry.py"],
}


def changed(base: str, head: str) -> list[str]:
    if not base:
        return []
    output = subprocess.check_output(["git", "diff", "--name-only", f"{base}...{head}"], text=True)
    return output.splitlines()


def select(paths: list[str]) -> list[str]:
    lowered = "\n".join(paths).lower()
    keys = [key for key in SOURCE_SUITES if key.replace("_", "") in lowered.replace("_", "")]
    if any(path in {"fuentes_publicas.json", "app/data/source-registry.json"} for path in paths):
        keys.append("registry")
    return list(dict.fromkeys(test for key in keys for test in SOURCE_SUITES[key]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    tests = select(changed(args.base, args.head))
    if not tests:
        tests = SOURCE_SUITES["registry"]
    for test in tests:
        print(f"SOURCE_TEST_START {test}", flush=True)
        subprocess.run([sys.executable, test], check=True)
    print(f"CHANGED_SOURCE_TESTS_OK count={len(tests)}")


if __name__ == "__main__":
    main()
