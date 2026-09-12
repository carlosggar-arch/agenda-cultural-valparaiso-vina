"""Append-only private decisions over exact guard inputs, not baseline losses.

The consumer must bind each before-event to its immutable handoff input and
independently verify the decision. An internally consistent hash is not enough.
These envelopes deliberately live outside the baseline ``receipts`` array.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Any

try:
    from app.scripts.recovery_disposition_ledger import _url, canonical_json_bytes, source_binding
except ModuleNotFoundError:
    from recovery_disposition_ledger import _url, canonical_json_bytes, source_binding

FIELD = 'candidate_quality_dispositions'
SCOPE = 'candidate_input_only_not_baseline_loss'
KINDS = {'quarantine': 'quarantined', 'non_event_exclusion': 'quarantined',
         'expiration': 'expired_removed', 'deduplication': 'duplicates_consolidated'}
FIELDS = {'schema_version', 'stage', 'scope', 'publication_date', 'kind',
          'event_binding', 'event_sha256', 'before_event', 'decision', 'transformation'}


def event_sha256(event: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(event)).hexdigest()


def _fail(reason: str) -> None:
    raise ValueError('CANDIDATE_QUALITY_DISPOSITION_' + reason)


def validate_candidate_quality_disposition(row: dict[str, Any]) -> None:
    from datetime import date

    if (not isinstance(row, dict) or set(row) != FIELDS or row.get('schema_version') != '1.0.0'
            or row.get('stage') != 'content_quality_guard' or row.get('scope') != SCOPE):
        _fail('CONTRACT_INVALID')
    if row['publication_date'] is not None:
        try:
            date.fromisoformat(row['publication_date'])
        except (ValueError, TypeError):
            _fail('CONTEXT_INVALID')
    event = row.get('before_event')
    if (not isinstance(event, dict) or not event.get('id')
            or row.get('event_binding') != source_binding(event)
            or row.get('event_sha256') != event_sha256(event)):
        _fail('SOURCE_BINDING_INVALID')
    operation, decision = row.get('transformation'), row.get('decision')
    if not isinstance(operation, dict) or not isinstance(decision, dict):
        _fail('DECISION_INVALID')
    action = operation.get('action')
    if (row.get('kind') != KINDS.get(action) or action not in KINDS
            or operation.get('stage') != row['stage'] or operation.get('source_record_id') != event['id']
            or not operation.get('reason')):
        _fail('DECISION_INVALID')
    if _url(operation.get('source_url')) not in set(row['event_binding']['source_urls']) | {''}:
        _fail('SOURCE_BINDING_INVALID')
    if action == 'expiration' and row['publication_date'] is None:
        _fail('CONTEXT_INVALID')
    destination = operation.get('destination')
    if not isinstance(destination, dict):
        _fail('DESTINATION_INVALID')
    if action == 'deduplication':
        if (event['id'] not in (decision.get('removed_ids') or [])
                or decision.get('kept_id') != operation.get('canonical_event_id')
                or destination != {'state': 'merged', 'canonical_event_id': decision.get('kept_id')}
                or not decision.get('kept_id') or decision['kept_id'] == event['id']):
            _fail('DESTINATION_INVALID')
    else:
        if decision.get('id') != event['id'] or decision.get('reason') != operation.get('reason'):
            _fail('DECISION_INVALID')
        state = 'expired' if action == 'expiration' else action
        if (destination.get('state') != state
                or destination.get('canonical_event_id') not in (None, event['id'])
                or operation.get('canonical_event_id') != event['id']):
            _fail('DESTINATION_INVALID')


def append_candidate_quality_dispositions(
    ledger: dict[str, Any], *, before_events: list[dict[str, Any]], after_events: list[dict[str, Any]],
    attempted_transformations: list[dict[str, Any]], changes: dict[str, Any], publication_date: str | None,
) -> None:
    """Capture only decisions actually made now; preserve earlier exact rows."""
    previous = ledger.get(FIELD, [])
    if not isinstance(previous, list):
        _fail('ROWS_INVALID')
    by_hash = {}
    for row in previous:
        validate_candidate_quality_disposition(row)
        key = row['event_sha256']
        if key in by_hash:
            _fail('DUPLICATE_INPUT')
        by_hash[key] = row
    before_by_id = {}
    for event in before_events:
        event_id = str(event.get('id') or '')
        if event_id in before_by_id:
            _fail('AMBIGUOUS_INPUT')
        before_by_id[event_id] = event
    after_ids = {str(event.get('id') or '') for event in after_events}
    additions = []
    seen_now = set()
    for operation in attempted_transformations:
        action = operation.get('action')
        if action not in KINDS:
            continue
        before = before_by_id.get(str(operation.get('source_record_id') or ''))
        if before is None:
            _fail('SOURCE_MISSING')
        if before['id'] in after_ids:
            _fail('SOURCE_STILL_PRESENT')
        kind = KINDS[action]
        decisions = [row for row in changes.get(kind, []) if (
            before['id'] in (row.get('removed_ids') or []) if action == 'deduplication'
            else row.get('id') == before['id'] and row.get('reason') == operation.get('reason'))]
        if len(decisions) != 1:
            _fail('DECISION_MISSING_OR_AMBIGUOUS')
        row = {'schema_version': '1.0.0', 'stage': 'content_quality_guard', 'scope': SCOPE,
               'publication_date': publication_date, 'kind': kind,
               'event_binding': source_binding(before), 'event_sha256': event_sha256(before),
               'before_event': copy.deepcopy(before), 'decision': copy.deepcopy(decisions[0]),
               'transformation': copy.deepcopy(operation)}
        validate_candidate_quality_disposition(row)
        key = row['event_sha256']
        if key in seen_now:
            _fail('DUPLICATE_DECISION')
        seen_now.add(key)
        existing = by_hash.get(key)
        if existing is not None:
            if existing != row:
                _fail('CONTRADICTORY_DECISION')
            continue
        by_hash[key] = row
        additions.append(row)
    # An exact formerly-terminal input cannot now survive unchanged while its
    # prior decision is silently reused as evidence that it was removed.
    for event in before_events:
        key = event_sha256(event)
        if key in by_hash and key not in seen_now and event.get('id') in after_ids:
            _fail('TERMINAL_INPUT_REINSERTED')
    if additions:
        ledger[FIELD] = [*previous, *sorted(additions, key=lambda row: (row['event_binding']['id'], row['event_sha256']))]
