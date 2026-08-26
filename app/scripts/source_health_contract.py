from __future__ import annotations

from datetime import datetime, timezone


DEFAULT_SLA_HOURS = {
    "instagram": 48.0,
    "website": 72.0,
    "web": 72.0,
    "calendar": 72.0,
    "feed": 48.0,
}


def parse_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def expected_sla_hours(source_type: object, role: object = None) -> float:
    kind = str(source_type or "").strip().casefold()
    source_role = str(role or "").strip().casefold()
    if source_role in {"venue", "cinema", "theatre", "theater", "sala"}:
        return 36.0
    return DEFAULT_SLA_HOURS.get(kind, 72.0)


def acquisition_snapshot(diag: dict | None, now: datetime, *, source_type: object = None, role: object = None) -> dict:
    diag = diag or {}
    last_attempt = (
        diag.get("last_attempt_at")
        or diag.get("last_fetch_at")
        or diag.get("refreshed_at")
    )
    last_success = (
        diag.get("last_success_at")
        or diag.get("last_successful_fetch_at")
        or diag.get("refreshed_at")
    )
    parsed_success = parse_time(last_success)
    age_hours = None
    if parsed_success is not None:
        age_hours = round((now.astimezone(timezone.utc) - parsed_success).total_seconds() / 3600.0, 1)

    raw_items = int(diag.get("raw_items") or diag.get("reviewed_titles") or 0)
    candidates = int(diag.get("candidate_events") or diag.get("sessions_detected") or 0)
    accepted = int(diag.get("accepted_events") or diag.get("sessions_published") or 0)
    published = int(diag.get("published_events") or diag.get("sessions_published") or 0)
    sla_hours = float(diag.get("expected_sla_hours") or expected_sla_hours(source_type, role))

    fetch_ok = diag.get("fetch_ok")
    state = str(diag.get("state") or "").strip().casefold()
    fetch_failed = fetch_ok is False or "fetch_error" in state or "transport" in state
    changed = diag.get("content_changed") is True
    stale = age_hours is not None and age_hours > sla_hours
    accepted_not_published = accepted > published
    content_changed_not_processed = changed and candidates == 0
    candidates_rejected = candidates > 0 and accepted == 0

    if accepted_not_published:
        health = "accepted_not_published"
        severity = "critical"
    elif fetch_failed:
        health = "fetch_failed"
        severity = "warning"
    elif content_changed_not_processed:
        health = "content_changed_not_processed"
        severity = "warning"
    elif candidates_rejected:
        health = "candidates_rejected"
        severity = "warning"
    elif stale:
        health = "stale"
        severity = "warning"
    elif parsed_success is None:
        health = "freshness_unknown"
        severity = "info"
    else:
        health = "healthy"
        severity = "ok"

    return {
        "health": health,
        "severity": severity,
        "expected_sla_hours": sla_hours,
        "last_attempt_at": last_attempt,
        "last_success_at": last_success,
        "age_hours": age_hours,
        "raw_items": raw_items,
        "candidate_events": candidates,
        "accepted_events": accepted,
        "published_events": published,
        "content_changed": changed,
        "rejection_reasons": diag.get("rejection_reasons") or [],
    }
