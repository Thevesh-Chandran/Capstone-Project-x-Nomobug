from datetime import date
import hashlib

import pytest
from scripts.service_programme_policy import programme_calendar


def inputs():
    raw = {'calendar_event_row': 1, 'calendar_id': 'example', 'event_id': 'paid-third',
           'start_raw': '2026-04-04T14:30:00+08:00', 'status': 'confirmed',
           'summary': 'GPC 3/3 Example complimentary'}
    review = {'event_identity_hash': hashlib.sha256(b'example|paid-third').hexdigest(),
        'expected_event_date': '2026-04-04', 'expected_session_current': '3',
        'expected_session_total': '3'}
    classified = {'calendar_event_row': 1, 'event_date_local': date(2026,4,4),
                  'event_category': 'complimentary', 'warranty_claim_candidate': False}
    return raw, review, classified


def test_owner_paid_third_visit_is_service_and_does_not_create_warranty_claim():
    raw, review, classified = inputs()
    result = programme_calendar([raw], [classified], [review])
    assert result[0]['event_category'] == 'service'
    assert result[0]['warranty_claim_candidate'] is False
    assert classified['event_category'] == 'complimentary'


@pytest.mark.parametrize('changes', [
    {'status': 'cancelled'}, {'summary': 'CANCELLED GPC 3/3'},
    {'summary': 'GPC 4/3'}, {'start_raw': '2026-04-05T14:30:00+08:00'},
    {'event_id': 'another-customer'},
])
def test_changed_reviewed_service_needs_source_review(changes):
    raw, review, classified = inputs()
    with pytest.raises(ValueError):
        programme_calendar([dict(raw, **changes)], [classified], [review])


def test_unreviewed_complimentary_visit_stays_complimentary():
    raw, _, classified = inputs()
    assert programme_calendar([raw], [classified], [])[0]['event_category'] == 'complimentary'


def test_future_review_is_not_required_before_scheduled_day():
    _, review, _ = inputs()
    assert programme_calendar([], [], [review], as_of=date(2026, 4, 3)) == []
    with pytest.raises(ValueError, match='missing from source'):
        programme_calendar([], [], [review], as_of=date(2026, 4, 4))


def test_conflicting_warranty_label_cannot_be_reclassified_as_paid():
    raw, review, classified = inputs()
    with pytest.raises(ValueError, match='conflicts'):
        programme_calendar([raw], [dict(classified, warranty_claim_candidate=True)], [review])
