import copy

import unittest

from apply_content_quality_guard import apply_guard
from candidate_quality_disposition_ledger import FIELD, append_candidate_quality_dispositions, event_sha256
from transformation_receipt_ledger import empty_ledger
from test_transformation_receipt_ledger import event


def sample():
    bad = event('bad', 'Pronto…')
    bad['description'] = None
    bad['location']['venue'] = None
    expired = event('past', 'Obra histórica', start='2026-08-01T19:00:00-04:00')
    return {'events': [bad, expired], 'publication_date': '2026-09-11', 'counts': {}}, empty_ledger()


def test_private_dispositions_keep_exact_input_and_survive_empty_second_report():
    dataset, ledger = sample()
    original = copy.deepcopy(dataset)
    first = apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')
    assert ledger['receipts'] == []
    assert {row['kind'] for row in ledger[FIELD]} == {'quarantined', 'expired_removed'}
    originals = {row['id']: row for row in original['events']}
    for row in ledger[FIELD]:
        assert row['before_event'] == originals[row['event_binding']['id']]
        assert row['event_sha256'] == event_sha256(row['before_event'])
    frozen = copy.deepcopy((dataset, ledger))
    second = apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')
    assert second['quarantined'] == second['expired_removed'] == []
    assert (dataset, ledger) == frozen
    apply_guard(original, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')
    assert (original, ledger) == frozen


def _assert_invalid_private_proof(mutation):
    dataset, ledger = sample()
    apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')
    row = ledger[FIELD][0]
    if mutation == 'hash': row['event_sha256'] = 'a' * 64
    if mutation == 'binding': row['event_binding']['schedule']['start'] = '2026-09-11T00:00:00-03:00'
    if mutation == 'source': row['transformation']['source_record_id'] = 'crossed'
    if mutation == 'url': row['transformation']['source_url'] = 'https://example.test/crossed'
    if mutation == 'destination': row['transformation']['destination']['canonical_event_id'] = 'crossed'
    if mutation == 'scope': row['scope'] = 'baseline_loss'
    if mutation == 'duplicate': ledger[FIELD].append(copy.deepcopy(row))
    with unittest.TestCase().assertRaisesRegex(ValueError, 'CANDIDATE_QUALITY_DISPOSITION_'):
        apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')


def test_missing_crossed_or_contradictory_private_proofs_fail_closed():
    for mutation in ('hash', 'binding', 'source', 'url', 'destination', 'scope', 'duplicate'):
        _assert_invalid_private_proof(mutation)


def test_report_without_actual_transformation_cannot_create_evidence():
    dataset, ledger = sample()
    append_candidate_quality_dispositions(ledger, before_events=dataset['events'], after_events=[],
        attempted_transformations=[], changes={'quarantined': [{'id': 'bad', 'reason': 'invented'}]}, publication_date='2026-09-11')
    assert FIELD not in ledger


def test_missing_original_input_rejected_without_appending():
    dataset, ledger = sample()
    apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')
    row = ledger[FIELD][0]
    fresh = empty_ledger()
    with unittest.TestCase().assertRaisesRegex(ValueError, 'SOURCE_MISSING'):
        append_candidate_quality_dispositions(fresh, before_events=[], after_events=[],
            attempted_transformations=[row['transformation']], changes={row['kind']: [row['decision']]}, publication_date='2026-09-11')
    assert fresh['receipts'] == [] and FIELD not in fresh


def test_deduplication_keeps_private_destination_and_all_functions():
    first = event('first', 'Concierto original', start='2026-09-12T19:00:00-03:00')
    first['schedule']['mode'] = 'dated'
    second = copy.deepcopy(first)
    second['id'] = 'second'
    second['source_url'] = second['links']['official'] = 'https://official.example/second'
    dataset = {'events': [first, second], 'publication_date': '2026-09-11'}
    ledger = empty_ledger()
    apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')
    assert len(dataset['events']) == len(ledger[FIELD]) == 1 and ledger['receipts'] == []
    row = ledger[FIELD][0]
    assert row['kind'] == 'duplicates_consolidated'
    assert row['transformation']['destination'] == {'state': 'merged', 'canonical_event_id': dataset['events'][0]['id']}
    expected = copy.deepcopy((dataset, ledger))
    apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')
    assert (dataset, ledger) == expected


def test_internally_consistent_changed_decision_is_rejected_on_same_original_input():
    dataset, ledger = sample()
    original = copy.deepcopy(dataset)
    apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')
    row = ledger[FIELD][0]
    row['decision']['reason'] = row['transformation']['reason'] = 'a_different_reason'
    with unittest.TestCase().assertRaisesRegex(ValueError, 'CONTRADICTORY_DECISION'):
        apply_guard(original, ledger=ledger, baseline_events=[], generated_at='2026-09-11T09:00:00-03:00')


def run_contract_tests():
    tests = [value for name, value in globals().items() if name.startswith('test_') and callable(value)]
    for test in tests:
        test()
    print(f'CANDIDATE_QUALITY_DISPOSITION_TESTS_OK count={len(tests)}')


if __name__ == '__main__':
    run_contract_tests()
