"""Account for guard dispositions without claiming public-baseline loss.

The original Core observation-recovery receipt is immutable. This closed
envelope references its canonical JSON hash and the candidate binding at guard entry.
It records a decision, not an assertion of editorial or temporal validity: the
Core consumer independently verifies the binding and temporal equivalence;
editorial predicates remain the responsibility of this guard's execution.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

try:
    from app.scripts.transformation_receipt_ledger import receipt_identity
except ModuleNotFoundError:
    from transformation_receipt_ledger import receipt_identity


DISPOSITION_ACTION = "recovery_disposition"
DISPOSITION_STAGE = "content_quality_guard"
DISPOSITION_VERSION = "1.0.0"
ENVELOPE_FIELDS = {
    "schema_version", "stage", "action", "observation_id",
    "recovery_receipt_sha256", "source_record_id", "source_binding",
    "transformations",
}
BINDING_FIELDS = {"id", "source_id", "source_urls", "title", "city", "venue", "schedule"}
SCHEDULE_FIELDS = {"mode", "start", "end", "occurrences"}
TERMINAL_ACTIONS = {"quarantine", "non_event_exclusion", "deduplication"}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def recovery_receipt_sha256(receipt: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(receipt)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _url(value: Any) -> str:
    return _text(value).rstrip("/").replace("https://instagram.com/", "https://www.instagram.com/", 1)


def source_binding(event: dict[str, Any]) -> dict[str, Any]:
    links = event.get("links") if isinstance(event.get("links"), dict) else {}
    location = event.get("location") if isinstance(event.get("location"), dict) else {}
    schedule = event.get("schedule") if isinstance(event.get("schedule"), dict) else {}
    return {
        "id": _text(event.get("id")),
        "source_id": _text(event.get("source_id")),
        "source_urls": sorted({url for value in (
            event.get("source_url"), links.get("source"), links.get("official"),
        ) if (url := _url(value))}),
        "title": _text(event.get("title")),
        "city": _text(location.get("city")),
        "venue": _text(location.get("venue_id") or location.get("venue")),
        "schedule": {key: copy.deepcopy(schedule.get(key)) for key in sorted(SCHEDULE_FIELDS)},
    }


def _fail(reason: str) -> None:
    # Values and source content never belong in exception messages.
    raise ValueError("RECOVERY_DISPOSITION_" + reason)


def _recoveries(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("action") != "observation_recovery":
            continue
        observation = _text(row.get("observation_id"))
        destination = row.get("destination")
        if (
            row.get("stage") != "finalizer_completeness_recovery"
            or not observation or row.get("source_record_id") != observation
            or not _text(row.get("source_id")) or not _url(row.get("source_url"))
            or not isinstance(destination, dict) or destination.get("state") != "published"
            or not _text(row.get("canonical_event_id"))
            or destination.get("canonical_event_id") != row.get("canonical_event_id")
        ):
            _fail("RECOVERY_BINDING_INVALID")
        if observation in result:
            _fail("RECOVERY_AMBIGUOUS")
        result[observation] = row
    return result


def _existing_dispositions(
    rows: list[dict[str, Any]], recoveries: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("action") != DISPOSITION_ACTION:
            continue
        observation = _text(row.get("observation_id"))
        recovery = recoveries.get(observation)
        binding = row.get("source_binding")
        transformations = row.get("transformations")
        if (
            set(row) != ENVELOPE_FIELDS or row.get("schema_version") != DISPOSITION_VERSION
            or row.get("stage") != DISPOSITION_STAGE or recovery is None
            or row.get("recovery_receipt_sha256") != recovery_receipt_sha256(recovery)
            or row.get("source_record_id") != recovery.get("canonical_event_id")
            or not isinstance(binding, dict) or set(binding) != BINDING_FIELDS
            or not isinstance(binding.get("schedule"), dict)
            or set(binding["schedule"]) != SCHEDULE_FIELDS
            or binding.get("id") != row.get("source_record_id")
            or not isinstance(transformations, list) or len(transformations) != 1
            or not isinstance(transformations[0], dict)
        ):
            _fail("EXISTING_EVIDENCE_INVALID")
        if observation in result:
            _fail("MULTIPLE_ACCOUNTING")
        result[observation] = row
    return result


def append_recovery_dispositions(
    ledger: dict[str, Any], *, before_events: list[dict[str, Any]],
    attempted_transformations: list[dict[str, Any]], after_events: list[dict[str, Any]],
) -> int:
    """Append one exact terminal operation per recovered observation.

    No publication decision or temporal-equivalence exception is made here.
    Multi-operation chains remain fail-closed until their intermediate binding
    can be represented and independently verified. Baseline receipts are never
    removed, replaced, or manufactured by this function.
    """
    rows = ledger.get("receipts")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        _fail("LEDGER_INVALID")
    recoveries = _recoveries(rows)
    existing = _existing_dispositions(rows, recoveries)
    if not recoveries:
        return 0
    before: dict[str, dict[str, Any]] = {}
    after: dict[str, dict[str, Any]] = {}
    for events, index in ((before_events, before), (after_events, after)):
        for event in events:
            event_id = _text(event.get("id"))
            if not event_id or event_id in index:
                _fail("CANDIDATE_IDENTITY_AMBIGUOUS")
            index[event_id] = event
    attempted: dict[str, list[dict[str, Any]]] = {}
    for operation in attempted_transformations:
        attempted.setdefault(_text(operation.get("source_record_id")), []).append(operation)
    pending: list[dict[str, Any]] = []
    for observation, recovery in sorted(recoveries.items()):
        original_id = recovery["canonical_event_id"]
        previous = existing.get(observation)
        if original_id not in before:
            # A subsequent pass must not silently lose a prior dedup survivor.
            if previous:
                prior = previous["transformations"][0]
                if prior.get("action") == "deduplication":
                    survivor = (prior.get("destination") or {}).get("canonical_event_id")
                    if attempted.get(_text(survivor)):
                        _fail("CHAIN_UNSUPPORTED")
                    if survivor not in after:
                        _fail("SURVIVOR_INVALID")
            continue
        operations = attempted.get(original_id, [])
        if not operations:
            if previous:
                _fail("CONTRADICTORY_REPEAT")
            if original_id not in after:
                _fail("UNEXPLAINED_DISAPPEARANCE")
            continue
        if len(operations) != 1:
            _fail("CHAIN_UNSUPPORTED")
        operation = operations[0]
        action = operation.get("action")
        destination = operation.get("destination")
        binding = source_binding(before[original_id])
        if (
            operation.get("stage") != DISPOSITION_STAGE or action not in TERMINAL_ACTIONS
            or not _text(operation.get("reason")) or not isinstance(destination, dict)
            or not binding["source_id"] or _url(recovery.get("source_url")) not in binding["source_urls"]
            or _url(operation.get("source_url")) not in binding["source_urls"]
            or original_id in after
        ):
            _fail("TRANSFORMATION_INVALID")
        if action == "deduplication":
            survivor = _text(destination.get("canonical_event_id"))
            if (
                destination.get("state") != "merged" or not survivor
                or survivor != operation.get("canonical_event_id")
                or survivor == original_id or survivor not in after
            ):
                _fail("SURVIVOR_INVALID")
            if attempted.get(survivor):
                _fail("CHAIN_UNSUPPORTED")
        elif (
            destination.get("state") != action
            or destination.get("canonical_event_id") not in (None, original_id)
        ):
            _fail("TERMINAL_DESTINATION_INVALID")
        envelope = {
            "schema_version": DISPOSITION_VERSION,
            "stage": DISPOSITION_STAGE,
            "action": DISPOSITION_ACTION,
            "observation_id": observation,
            "recovery_receipt_sha256": recovery_receipt_sha256(recovery),
            "source_record_id": original_id,
            "source_binding": binding,
            "transformations": [copy.deepcopy(operation)],
        }
        if previous is not None:
            if canonical_json_bytes(previous) != canonical_json_bytes(envelope):
                _fail("CONTRADICTORY_REPEAT")
        else:
            pending.append(envelope)
    if pending:
        rows.extend(pending)
        rows.sort(key=lambda row: (receipt_identity(row), _text(row.get("observation_id"))))
    return len(pending)
