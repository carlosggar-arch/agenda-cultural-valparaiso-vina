from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANONICAL_DATASETS = {
    "valparaiso": Path("agenda_web.json"),
    "gijon": Path("app/data/gijon/agenda_web.json"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"SOURCE_REFRESH_INVALID_DATASET path={path}: {exc}") from exc
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise SystemExit(f"SOURCE_REFRESH_INVALID_DATASET_SHAPE path={path}")
    return payload


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for city, relative_path in CANONICAL_DATASETS.items():
        path = root / relative_path
        events = _load_dataset(path)
        result[city] = {
            "path": relative_path.as_posix(),
            "sha256": _sha256(path),
            "events": len(events),
        }
    return result


def evaluate(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    allowed_cities: set[str],
) -> dict[str, Any]:
    known = set(CANONICAL_DATASETS)
    if set(before) != known or set(after) != known:
        raise SystemExit("SOURCE_REFRESH_SNAPSHOT_CITY_SET_INVALID")
    unknown_allowed = allowed_cities - known
    if unknown_allowed:
        raise SystemExit("SOURCE_REFRESH_ALLOWED_CITY_UNKNOWN=" + ",".join(sorted(unknown_allowed)))

    changed = sorted(
        city for city in known if before[city].get("sha256") != after[city].get("sha256")
    )
    unexpected = sorted(set(changed) - allowed_cities)
    if unexpected:
        raise SystemExit(
            "SOURCE_REFRESH_UNTOUCHED_CITY_CHANGED=" + ",".join(unexpected)
        )

    status = "no_change" if not changed else "candidate"
    return {
        "status": status,
        "changed_cities": changed,
        "allowed_cities": sorted(allowed_cities),
        "before": before,
        "after": after,
    }


def baseline_is_current(expected: str, actual: str) -> bool:
    return bool(expected) and expected == actual


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _snapshot_command(args: argparse.Namespace) -> None:
    result = snapshot(Path(args.root))
    write_json(Path(args.output), result)
    print("SOURCE_REFRESH_SNAPSHOT_OK " + " ".join(f"{city}={data['sha256']}" for city, data in sorted(result.items())))


def _evaluate_command(args: argparse.Namespace) -> None:
    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = snapshot(Path(args.root))
    decision = evaluate(before, after, set(args.allowed_city))
    write_json(Path(args.output), decision)
    if decision["status"] == "no_change":
        print("SOURCE_REFRESH_NO_CHANGE")
    else:
        print("SOURCE_REFRESH_CANDIDATE_OK changed_cities=" + ",".join(decision["changed_cities"]))


def _baseline_command(args: argparse.Namespace) -> None:
    if not baseline_is_current(args.expected, args.actual):
        raise SystemExit(
            f"SOURCE_REFRESH_BASELINE_STALE expected={args.expected} actual={args.actual}"
        )
    print(f"SOURCE_REFRESH_BASELINE_OK sha={args.expected}")


def _provenance_command(args: argparse.Namespace) -> None:
    decision = json.loads(Path(args.decision).read_text(encoding="utf-8"))
    if decision.get("status") != "candidate":
        raise SystemExit("SOURCE_REFRESH_PROVENANCE_REQUIRES_CANDIDATE")
    adapters = [value.strip() for value in args.adapters.split(",") if value.strip()]
    payload = {
        "schema_version": 1,
        "producer": "source-refresh.yml",
        "baseline_sha": args.baseline,
        "mode": args.mode,
        "adapters": adapters,
        "changed_cities": decision.get("changed_cities", []),
        "canonical_before": decision.get("before", {}),
        "canonical_after": decision.get("after", {}),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(Path(args.output), payload)
    print("SOURCE_REFRESH_PROVENANCE_OK baseline=" + args.baseline)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed guard for automatic source-refresh candidates.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--root", default=".")
    snapshot_parser.add_argument("--output", required=True)
    snapshot_parser.set_defaults(func=_snapshot_command)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--root", default=".")
    evaluate_parser.add_argument("--before", required=True)
    evaluate_parser.add_argument("--output", required=True)
    evaluate_parser.add_argument("--allowed-city", action="append", required=True)
    evaluate_parser.set_defaults(func=_evaluate_command)

    baseline_parser = subparsers.add_parser("check-baseline")
    baseline_parser.add_argument("--expected", required=True)
    baseline_parser.add_argument("--actual", required=True)
    baseline_parser.set_defaults(func=_baseline_command)

    provenance_parser = subparsers.add_parser("provenance")
    provenance_parser.add_argument("--decision", required=True)
    provenance_parser.add_argument("--baseline", required=True)
    provenance_parser.add_argument("--mode", required=True)
    provenance_parser.add_argument("--adapters", required=True)
    provenance_parser.add_argument("--output", required=True)
    provenance_parser.set_defaults(func=_provenance_command)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
