from __future__ import annotations

from datetime import datetime, time, timezone
import hashlib
from zoneinfo import ZoneInfo


VALPO_CATEGORY_LABELS = {
    "teatro": "Teatro",
    "literatura": "Literatura",
}
VALPO_SEMANTIC_CAPABILITIES = tuple(VALPO_CATEGORY_LABELS)
GIJON_CATEGORY_LABELS = {"exposiciones": "Exposiciones"}


def _parse_instant(value: object, zone: ZoneInfo, *, end_of_day: bool = False) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if len(text) == 10:
        parsed = datetime.combine(parsed.date(), time.max if end_of_day else time.min)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(timezone.utc)


def _event_active_until(
    event: dict[str, object], reference: datetime, *, default_timezone: str
) -> datetime | None:
    schedule = event.get("schedule") or {}
    if not isinstance(schedule, dict):
        return None
    try:
        zone = ZoneInfo(str(schedule.get("timezone") or default_timezone))
    except Exception:
        return None
    boundaries = []
    for occurrence in schedule.get("occurrences") or []:
        if not isinstance(occurrence, dict):
            continue
        boundary = _parse_instant(occurrence.get("end") or occurrence.get("start"), zone, end_of_day=True)
        if boundary:
            boundaries.append(boundary)
    end = _parse_instant(schedule.get("end"), zone, end_of_day=True)
    start = _parse_instant(schedule.get("start"), zone)
    boundaries.extend(boundary for boundary in (end, start) if boundary)
    future = [boundary for boundary in boundaries if boundary >= reference]
    return max(future) if future else None


def select_category_semantic_cases(
    dataset: dict[str, object],
    category_labels: dict[str, str],
    *,
    default_timezone: str,
    reference: datetime | None = None,
) -> list[dict[str, str]]:
    events = dataset.get("events")
    if not isinstance(events, list):
        raise SystemExit("PRODUCTION_VALPO_SEMANTIC_DATASET_INVALID")
    effective = (reference or datetime.now(timezone.utc)).astimezone(timezone.utc)
    selected = []
    for category_id in category_labels:
        eligible = []
        for event in events:
            if not isinstance(event, dict) or event.get("event_type") != "event":
                continue
            if str((event.get("primary_category") or {}).get("id") or "") != category_id:
                continue
            event_id = str(event.get("id") or "").strip()
            title = str(event.get("title") or "").strip()
            source_id = str(event.get("source_id") or "").strip()
            links = event.get("links") or {}
            official = str(links.get("official") or links.get("source") or "").strip()
            active_until = _event_active_until(event, effective, default_timezone=default_timezone)
            if not event_id or not title or not source_id or not official.startswith("https://") or not active_until:
                continue
            eligible.append((active_until, event_id, title))
        if not eligible:
            raise SystemExit(
                f"PRODUCTION_VALPO_SEMANTIC_CAPABILITY_MISSING category={category_id} "
                "requirements=active_schedule,canonical_title,official_provenance"
            )
        active_until, event_id, title = max(eligible, key=lambda row: (row[0], row[1]))
        selected.append(
            {
                "id": event_id,
                "category_id": category_id,
                "category_label": category_labels[category_id],
                "title": title,
                "active_until": active_until.isoformat(),
            }
        )
    return selected


def select_valpo_semantic_cases(
    dataset: dict[str, object], *, reference: datetime | None = None
) -> list[dict[str, str]]:
    return select_category_semantic_cases(
        dataset,
        VALPO_CATEGORY_LABELS,
        default_timezone="America/Santiago",
        reference=reference,
    )


def select_gijon_semantic_case(
    dataset: dict[str, object], *, reference: datetime | None = None
) -> dict[str, str]:
    return select_category_semantic_cases(
        dataset,
        GIJON_CATEGORY_LABELS,
        default_timezone="Europe/Madrid",
        reference=reference,
    )[0]


def assert_semantic_dataset_identity(snapshots: dict[str, bytes]) -> str:
    by_hash: dict[str, list[str]] = {}
    for origin, body in snapshots.items():
        by_hash.setdefault(hashlib.sha256(body).hexdigest(), []).append(origin)
    if len(by_hash) != 1:
        detail = ",".join(
            f"{digest}:{'+'.join(sorted(origins))}" for digest, origins in sorted(by_hash.items())
        )
        raise SystemExit(f"PRODUCTION_SEMANTIC_DATASET_DIVERGENCE hashes={detail}")
    return next(iter(by_hash))
