from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.semantic_quality_audit import build_report

DEFAULT_LATEST = Path("app/data/quality/semantic-quality-latest.json")
DEFAULT_HISTORY = Path("app/data/quality/semantic-source-history.json")
SCHEMA_VERSION = "1.0.0"
MAX_SNAPSHOTS = 120


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def canonical_payload(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": report.get("summary", {}),
        "source_metrics": report.get("source_metrics", {}),
    }


def report_fingerprint(report: dict[str, Any]) -> str:
    raw = json.dumps(canonical_payload(report), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compact_snapshot(report: dict[str, Any], source_ref: str | None, generated_at: str) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "source_ref": source_ref,
        "fingerprint": report_fingerprint(report),
        "summary": report.get("summary", {}),
        "source_metrics": report.get("source_metrics", {}),
    }


def update_history(
    report: dict[str, Any],
    existing: dict[str, Any] | None,
    source_ref: str | None,
    generated_at: str,
    max_snapshots: int = MAX_SNAPSHOTS,
) -> dict[str, Any]:
    history = {
        "schema_version": SCHEMA_VERSION,
        "snapshots": list((existing or {}).get("snapshots", [])),
    }
    snapshot = compact_snapshot(report, source_ref, generated_at)
    snapshots = history["snapshots"]
    if not snapshots or snapshots[-1].get("fingerprint") != snapshot["fingerprint"]:
        snapshots.append(snapshot)
    elif source_ref and snapshots[-1].get("source_ref") != source_ref:
        # Same observable quality state at a new canonical publication: retain the
        # latest producer reference without manufacturing a duplicate trend point.
        snapshots[-1] = {**snapshots[-1], "source_ref": source_ref, "generated_at": generated_at}
    history["snapshots"] = snapshots[-max(1, int(max_snapshots)):]
    return history


def latest_payload(report: dict[str, Any], source_ref: str | None, generated_at: str) -> dict[str, Any]:
    return {
        **report,
        "history_schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_ref": source_ref,
        "fingerprint": report_fingerprint(report),
    }


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def trend_rows(history: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots = history.get("snapshots", [])
    if len(snapshots) < 2:
        return []
    before, current = snapshots[-2], snapshots[-1]
    rows = []
    keys = set(before.get("source_metrics", {})) | set(current.get("source_metrics", {}))
    for key in sorted(keys):
        old = before.get("source_metrics", {}).get(key, {})
        new = current.get("source_metrics", {}).get(key, {})
        old_rate = float(old.get("unclassified_rate", 0.0))
        new_rate = float(new.get("unclassified_rate", 0.0))
        delta = new_rate - old_rate
        if abs(delta) < 1e-9 and old.get("dominant_category") == new.get("dominant_category"):
            continue
        rows.append({
            "source_key": key,
            "city_id": new.get("city_id") or old.get("city_id"),
            "source_name": new.get("source_name") or old.get("source_name"),
            "old_rate": old_rate,
            "new_rate": new_rate,
            "delta": delta,
            "old_dominant": old.get("dominant_category"),
            "new_dominant": new.get("dominant_category"),
        })
    return sorted(rows, key=lambda row: (-abs(row["delta"]), str(row["city_id"]), str(row["source_name"])))


def render_trend_markdown(history: dict[str, Any]) -> str:
    snapshots = history.get("snapshots", [])
    lines = ["# Tendencia de calidad semántica", ""]
    if not snapshots:
        return "\n".join(lines + ["Todavía no existe un snapshot canónico.", ""])
    current = snapshots[-1]
    summary = current.get("summary", {})
    lines.append(
        f"Snapshot canónico: `{current.get('source_ref') or 'sin-ref'}` · "
        f"eventos **{summary.get('total_events', 0)}** · "
        f"sin clasificar **{summary.get('unclassified_count', 0)}** "
        f"({float(summary.get('unclassified_rate', 0.0)):.1%})."
    )
    rows = trend_rows(history)
    if len(snapshots) < 2:
        lines.extend(["", "Aún no hay dos snapshots distintos para calcular tendencia.", ""])
        return "\n".join(lines)
    lines.extend(["", "| Ciudad | Fuente | Sin clasificar antes → ahora | Dominante antes → ahora |", "| --- | --- | --- | --- |"])
    if not rows:
        lines.append("| — | — | Sin cambios | Sin cambios |")
    else:
        for row in rows[:40]:
            lines.append(
                f"| {row['city_id'] or '—'} | {str(row['source_name'] or '—').replace('|', '\\|')} | "
                f"{row['old_rate']:.1%} → {row['new_rate']:.1%} | "
                f"{row['old_dominant'] or '—'} → {row['new_dominant'] or '—'} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist compact semantic quality history under the canonical public writer.")
    parser.add_argument("--latest-path", default=str(DEFAULT_LATEST))
    parser.add_argument("--history-path", default=str(DEFAULT_HISTORY))
    parser.add_argument("--markdown-output", default=None)
    parser.add_argument("--source-ref", default=os.environ.get("SOURCE_HEAD_SHA") or os.environ.get("GITHUB_SHA"))
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--max-snapshots", type=int, default=MAX_SNAPSHOTS)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    latest_path = resolve_path(args.latest_path)
    history_path = resolve_path(args.history_path)
    report = build_report()
    existing = load_json(history_path)
    history = update_history(report, existing, args.source_ref, generated_at, args.max_snapshots)
    latest = latest_payload(report, args.source_ref, generated_at)

    if not args.no_write:
        write_json(latest_path, latest)
        write_json(history_path, history)
    if args.markdown_output:
        output = resolve_path(args.markdown_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_trend_markdown(history), encoding="utf-8")

    print(
        "SEMANTIC_QUALITY_HISTORY_OK "
        f"snapshots={len(history['snapshots'])} sources={len(report.get('source_metrics', {}))} "
        f"write={str(not args.no_write).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
