from __future__ import annotations

from datetime import datetime, timezone


DEFAULT_SLA_HOURS = {
    "instagram": 48.0,
    "website": 72.0,
    "web": 72.0,
    "calendar": 72.0,
    "feed": 48.0,
}

CANONICAL_RECEIPT_SCHEMA_VERSION = "1.0.0"


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


def _first(diag: dict, *keys: str):
    for key in keys:
        value = diag.get(key)
        if value is not None and value != "":
            return value
    return None


def _count(diag: dict, *keys: str) -> int:
    value = _first(diag, *keys)
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def canonical_acquisition_receipt(diag: dict | None) -> dict:
    """Normalize source-specific/legacy diagnostics without changing publication policy.

    `refreshed_at` is accepted as legacy acquisition evidence only when the row is
    not preservation-only, or when an explicit `fetch_ok: true` proves that a real
    fetch succeeded. This prevents preservation of old public events from making a
    source look freshly acquired.
    """
    diag = diag if isinstance(diag, dict) else {}
    preserved_existing = bool(diag.get("preserved_existing"))
    fetch_ok = diag.get("fetch_ok")

    last_attempt = _first(diag, "last_attempt_at", "last_fetch_at", "refreshed_at")
    last_success = _first(diag, "last_success_at", "last_successful_fetch_at")
    if last_success is None and (not preserved_existing or fetch_ok is True):
        last_success = _first(diag, "refreshed_at")

    raw_items = _count(diag, "raw_items", "reviewed_titles")
    candidates = _count(
        diag,
        "candidate_events",
        "sessions_detected",
        "events_detected",
    )
    accepted = _count(
        diag,
        "accepted_events",
        "sessions_published",
        "events_published",
    )
    published = _count(
        diag,
        "published_events",
        "sessions_published",
        "events_published",
    )

    evidence_keys = {
        "last_attempt_at",
        "last_fetch_at",
        "refreshed_at",
        "last_success_at",
        "last_successful_fetch_at",
        "fetch_ok",
        "state",
        "raw_items",
        "reviewed_titles",
        "candidate_events",
        "sessions_detected",
        "events_detected",
        "accepted_events",
        "sessions_published",
        "events_published",
        "published_events",
        "content_changed",
        "rejection_reasons",
    }
    receipt_present = any(key in diag for key in evidence_keys)

    return {
        "receipt_schema_version": CANONICAL_RECEIPT_SCHEMA_VERSION,
        "receipt_present": receipt_present,
        "last_attempt_at": last_attempt,
        "last_success_at": last_success,
        "fetch_ok": fetch_ok,
        "state": str(diag.get("state") or "").strip(),
        "raw_items": raw_items,
        "candidate_events": candidates,
        "accepted_events": accepted,
        "published_events": published,
        "content_changed": diag.get("content_changed") is True,
        "rejection_reasons": diag.get("rejection_reasons") or [],
        "preserved_existing": preserved_existing,
    }


def acquisition_snapshot(
    diag: dict | None,
    now: datetime,
    *,
    source_type: object = None,
    role: object = None,
) -> dict:
    receipt = canonical_acquisition_receipt(diag)
    parsed_success = parse_time(receipt["last_success_at"])
    age_hours = None
    if parsed_success is not None:
        age_hours = round(
            (now.astimezone(timezone.utc) - parsed_success).total_seconds() / 3600.0,
            1,
        )

    candidates = receipt["candidate_events"]
    accepted = receipt["accepted_events"]
    published = receipt["published_events"]
    sla_hours = float(
        (diag or {}).get("expected_sla_hours")
        or expected_sla_hours(source_type, role)
    )

    state = receipt["state"].casefold()
    fetch_failed = receipt["fetch_ok"] is False or "fetch_error" in state or "transport" in state
    changed = receipt["content_changed"]
    stale = age_hours is not None and age_hours > sla_hours
    accepted_not_published = accepted > published
    content_changed_not_processed = changed and candidates == 0
    candidates_rejected = candidates > 0 and accepted == 0

    # Publication policy is intentionally asymmetric:
    # - acquisition/observability problems degrade one source and remain warnings;
    # - deterministic accepted -> published loss is fail-closed.
    publication_blocking = accepted_not_published

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
        severity = "warning"
    else:
        health = "healthy"
        severity = "ok"

    return {
        "health": health,
        "severity": severity,
        "publication_blocking": publication_blocking,
        "expected_sla_hours": sla_hours,
        "age_hours": age_hours,
        **receipt,
    }
