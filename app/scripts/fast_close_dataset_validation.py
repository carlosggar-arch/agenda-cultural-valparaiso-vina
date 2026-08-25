from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASETS = (
    ("valparaiso", Path("agenda_web.json")),
    ("gijon", Path("app/data/gijon/agenda_web.json")),
)


def load_payload(path: Path) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def load_payload_from_ref(ref: str, path: Path) -> dict | None:
    if not ref:
        return None
    try:
        raw = subprocess.check_output(
            ["git", "show", f"{ref}:{path.as_posix()}"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None
    return json.loads(raw)


def changed_paths(base_ref: str) -> set[str]:
    if not base_ref:
        return {path.as_posix() for _, path in DATASETS}
    output = subprocess.check_output(
        ["git", "diff", "--name-only", base_ref, "HEAD"], cwd=ROOT, text=True
    )
    return {line.strip() for line in output.splitlines() if line.strip()}


def requires_freshness(*, changed: bool, current_generated_at: str, previous_generated_at: str | None) -> bool:
    if not changed:
        return False
    if previous_generated_at is None:
        return True
    return current_generated_at != previous_generated_at


def validate_payload(
    city: str,
    payload: dict,
    *,
    require_fresh: bool,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    events = payload.get("events") or []
    ids = [str(event.get("id") or "").strip() for event in events if isinstance(event, dict)]
    if len(ids) != len(events) or any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"FAST_CLOSE_IDS_INVALID city={city}")

    counts = payload.get("counts") or {}
    if counts.get("total") is not None and int(counts.get("total")) != len(events):
        raise ValueError(
            f"FAST_CLOSE_COUNT_MISMATCH city={city} declared={counts.get('total')} actual={len(events)}"
        )

    generated_raw = str(payload.get("generated_at") or "").strip()
    publication_date = str(payload.get("publication_date") or "")[:10]
    timezone_name = str(payload.get("timezone") or "").strip()
    if not generated_raw or not publication_date or not timezone_name:
        raise ValueError(f"FAST_CLOSE_METADATA_MISSING city={city}")

    generated = datetime.fromisoformat(generated_raw.replace("Z", "+00:00"))
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=ZoneInfo(timezone_name))
    generated_local = generated.astimezone(ZoneInfo(timezone_name))
    expected_publication_date = generated_local.date().isoformat()
    if publication_date != expected_publication_date:
        raise ValueError(
            f"FAST_CLOSE_PUBLICATION_DATE_MISMATCH city={city} publication_date={publication_date} "
            f"generated_local={expected_publication_date}"
        )

    age_label = "not-required"
    if require_fresh:
        now = now_utc or datetime.now(timezone.utc)
        age_hours = (now - generated.astimezone(timezone.utc)).total_seconds() / 3600
        if age_hours < -0.25 or age_hours > 6:
            raise ValueError(f"FAST_CLOSE_DATASET_STALE city={city} age_hours={age_hours:.2f}")
        age_label = f"{age_hours:.2f}"

    return {
        "events": len(events),
        "publication_date": publication_date,
        "age_hours": age_label,
        "freshness_required": require_fresh,
        "generated_at": generated_raw,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate production dataset identity and require freshness only for actual regenerations."
    )
    parser.add_argument("--base-ref", default="")
    args = parser.parse_args()

    changed = changed_paths(args.base_ref)
    for city, path in DATASETS:
        payload = load_payload(path)
        previous = load_payload_from_ref(args.base_ref, path)
        current_generated = str(payload.get("generated_at") or "").strip()
        previous_generated = None if previous is None else str(previous.get("generated_at") or "").strip()
        path_changed = path.as_posix() in changed
        require_fresh = requires_freshness(
            changed=path_changed,
            current_generated_at=current_generated,
            previous_generated_at=previous_generated,
        )
        try:
            result = validate_payload(city, payload, require_fresh=require_fresh)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        print(
            f"FAST_CLOSE_DATASET_OK city={city} events={result['events']} "
            f"publication_date={result['publication_date']} age_hours={result['age_hours']} "
            f"changed={str(path_changed).lower()} generation_changed={str(require_fresh).lower()} "
            f"freshness_required={str(require_fresh).lower()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
