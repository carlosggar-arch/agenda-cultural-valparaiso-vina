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
import re
import unicodedata
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
OBSERVATION_EVIDENCE_FIELDS = {"transformation_class", "observation_binding", "canonical_binding"}


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


def _fold(value: str) -> str:
    return " ".join("".join(char for char in unicodedata.normalize("NFKD", str(value))
                            if not unicodedata.combining(char)).casefold().split())


def _valid_binding(binding: Any) -> bool:
    if not isinstance(binding, dict) or set(binding) != BINDING_FIELDS:
        return False
    if any(not isinstance(binding.get(key), str) for key in ("id", "source_id", "title", "city", "venue")):
        return False
    urls, schedule = binding.get("source_urls"), binding.get("schedule")
    return bool(
        binding["id"] and binding["source_id"]
        and isinstance(urls, list) and urls
        and all(isinstance(value, str) and value and _url(value) == value for value in urls)
        and urls == sorted(set(urls))
        and isinstance(schedule, dict) and set(schedule) == SCHEDULE_FIELDS
    )


def _same_observation_projection(observed: dict, canonical: dict, *, shared_capture: bool = False) -> bool:
    """An exact repeated post is not a temporal deduplication inference.

    Distinct URLs must instead prove a complete, known function identity through
    the same validator as the guard. Import lazily because the guard calls this
    module only after its own definitions have loaded.
    """
    if set(observed["source_urls"]) & set(canonical["source_urls"]):
        fields = ("title", "city", "schedule") if shared_capture else ("title", "city", "venue", "schedule")
        return all(observed[key] == canonical[key] for key in fields)
    if shared_capture:
        return False
    if any(not _fold(observed[key]) or _fold(observed[key]) != _fold(canonical[key])
           for key in ("title", "city", "venue")):
        return False
    try:
        from app.scripts.apply_content_quality_guard import temporal_identity
    except ModuleNotFoundError:
        from apply_content_quality_guard import temporal_identity
    observed_time = temporal_identity({"schedule": observed["schedule"]})
    canonical_time = temporal_identity({"schedule": canonical["schedule"]})
    return observed_time is not None and observed_time == canonical_time


def _observation_proof(recovery: dict) -> tuple[dict, dict] | None:
    evidence = recovery.get("evidence") or {}
    if not isinstance(evidence, dict):
        _fail("RECOVERY_BINDING_INVALID")
    if not ({"observation_binding", "canonical_binding", "shared_capture"} & set(evidence)):
        return None  # Legacy single-observation parents remain compatible.
    shared = evidence.get("shared_capture")
    # Core independently reprojects both captured observations and checks this
    # material hash. Here it may bypass only account-derived venue differences
    # for the same post, never a distinct title, city, or complete schedule.
    if "shared_capture" in evidence and (
        not isinstance(shared, dict) or set(shared) != {"canonical_observation_id", "material_sha256"}
        or not re.fullmatch(r"obs_[a-zA-Z0-9_]+", str(shared.get("canonical_observation_id") or ""))
        or shared.get("canonical_observation_id") == recovery.get("observation_id")
        or not re.fullmatch(r"[0-9a-f]{64}", str(shared.get("material_sha256") or ""))
    ):
        _fail("RECOVERY_BINDING_INVALID")
    observed, canonical = evidence.get("observation_binding"), evidence.get("canonical_binding")
    if (set(evidence) not in (OBSERVATION_EVIDENCE_FIELDS, OBSERVATION_EVIDENCE_FIELDS | {"shared_capture"})
            or evidence.get("transformation_class") != "recovered"
            or not _valid_binding(observed) or not _valid_binding(canonical)
            or canonical["id"] != recovery.get("canonical_event_id")
            or _url(recovery.get("source_url")) not in observed["source_urls"]
            or not _same_observation_projection(observed, canonical, shared_capture=shared is not None)):
        _fail("RECOVERY_BINDING_INVALID")
    return observed, canonical


def _parent_matches_binding(recovery: dict, binding: dict) -> bool:
    proof = _observation_proof(recovery)
    if proof is None:
        return _url(recovery.get("source_url")) in binding["source_urls"]
    if proof[1] != binding:
        _fail("RECOVERY_BINDING_INVALID")
    return True


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
        _observation_proof(row)
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
        if _observation_proof(recovery) is not None and not _parent_matches_binding(recovery, binding):
            _fail("EXISTING_EVIDENCE_INVALID")
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
        binding = source_binding(before[original_id])
        # Proof-bearing parents bind retained observations too. A guard that
        # takes no action must not silently accept a crossed canonical proof.
        parent_matches = _parent_matches_binding(recovery, binding)
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
        if (
            operation.get("stage") != DISPOSITION_STAGE or action not in TERMINAL_ACTIONS
            or not _text(operation.get("reason")) or not isinstance(destination, dict)
            or not binding["source_id"] or not parent_matches
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
        recorded_operation = copy.deepcopy(operation)
        if action == "deduplication" and _observation_proof(recovery) is not None:
            combined = recorded_operation.get("combined_provenance")
            sources = combined.get("sources") if isinstance(combined, dict) else None
            if not isinstance(sources, list) or any(not isinstance(value, str) for value in sources):
                _fail("TRANSFORMATION_INVALID")
            own_url = _url(recovery["source_url"])
            if own_url not in {_url(value) for value in sources}:
                sources.append(own_url)
        envelope = {
            "schema_version": DISPOSITION_VERSION,
            "stage": DISPOSITION_STAGE,
            "action": DISPOSITION_ACTION,
            "observation_id": observation,
            "recovery_receipt_sha256": recovery_receipt_sha256(recovery),
            "source_record_id": original_id,
            "source_binding": binding,
            "transformations": [recorded_operation],
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
