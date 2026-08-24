from __future__ import annotations

import argparse
import json
from pathlib import Path

from production_certification_history import (
    ENVIRONMENT,
    VERIFIED_STATE,
    CertificationHistoryError,
    validate_history,
)


def check_certification(state_root: Path, expected_head: str, expected_release: int) -> dict:
    history = validate_history(state_root)
    rows = history.get("certifications") or []
    matches = [
        row
        for row in rows
        if str(row.get("head_sha") or "") == expected_head
        and int(row.get("release") or 0) == expected_release
        and row.get("publication_state") == VERIFIED_STATE
    ]
    if not matches:
        latest = history.get("latest") or {}
        raise CertificationHistoryError(
            "PRODUCTION_UNCERTIFIED "
            f"expected_head={expected_head} expected_release=v{expected_release} "
            f"certified_head={latest.get('head_sha') or 'none'} "
            f"certified_release=v{latest.get('release') or 'none'}"
        )
    match = matches[0]
    if not match.get("archive_sha256"):
        raise CertificationHistoryError("PRODUCTION_UNCERTIFIED archive_hash_missing")
    return match


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail closed when a deployed production head lacks a durable certification.")
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-release", required=True, type=int)
    args = parser.parse_args()

    try:
        match = check_certification(Path(args.state_root), args.expected_head, args.expected_release)
        print(
            "PRODUCTION_CERTIFICATION_WATCHDOG_OK "
            f"head={args.expected_head} release=v{args.expected_release} "
            f"archive={match['path']} sha256={match['archive_sha256']} environment={ENVIRONMENT}"
        )
        return 0
    except (CertificationHistoryError, json.JSONDecodeError, OSError, ValueError) as exc:
        message = str(exc)
        if not message.startswith("PRODUCTION_UNCERTIFIED"):
            message = f"PRODUCTION_UNCERTIFIED integrity_error={message}"
        print(message)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
