from datetime import date
import hashlib

import pytest
from scripts.service_programme_policy import programme_calendar


def inputs():
    raw = {'calendar_event_row': 1, 'calendar_id': 'example', 'event_id': 'paid-third',
           'start_raw': '2026-04-04T14:30:00+08:00', 'status': 'confirmed',
           'summary': 'GPC 3/3 Example complimentary', 'ical_uid': 'stable-uid'}
    review = {'event_identity_hash': hashlib.sha256(b'example|paid-third').hexdigest(),
        'ical_uid_hash': hashlib.sha256(b'stable-uid').hexdigest(),
        'programme_id': 'EXAMPLE', 'paid_programme_stage': '3',
        'expected_matched_sales_record_id': 'EXAMPLE_SALE', 'expected_event_date': '2026-04-04', 'expected_session_current': '3',
        'expected_session_total': '3'}
    classified = {'calendar_event_row': 1, 'event_date_local': date(2026,4,4),
                  'event_category': 'complimentary', 'warranty_claim_candidate': False,
                  'sales_record_id': 'EXAMPLE_SALE'}
    return raw, review, classified


def test_owner_paid_third_visit_is_service_and_does_not_create_warranty_claim():
    raw, review, classified = inputs()
    result = programme_calendar([raw], [classified], [review])
    assert result[0]['event_category'] == 'service'
    assert result[0]['warranty_claim_candidate'] is False
    assert classified['event_category'] == 'complimentary'


@pytest.mark.parametrize('changes', [
    {},
    {'calendar_id': 'new-team', 'event_id': 'new-id'},
])
def test_rescheduled_or_transferred_visit_uses_current_date(changes):
    raw, review, classified = inputs()
    event = dict(raw, start_raw='2026-04-05T14:30:00+08:00', **changes)
    result = programme_calendar([event], [dict(classified, event_date_local=date(2026, 4, 5))], [review])
    assert result[0]['event_category'] == 'service'
    assert result[0]['event_date_local'] == date(2026, 4, 5)


@pytest.mark.parametrize('changes', [
    {'status': 'cancelled'}, {'summary': 'CANCELLED GPC 3/3'},
    {'summary': 'GPC 4/3'}, {'event_id': 'new-id', 'ical_uid': 'new-uid'},
    {'event_id': 'new-id', 'recurring_event_id': 'shared-series'},
])
def test_unverified_changes_are_reported_without_applying_override(changes):
    raw, review, classified = inputs()
    issues = []
    result = programme_calendar([dict(raw, **changes)], [classified], [review], review_issues=issues)
    assert not result[0]['owner_confirmed_paid_stage']
    assert issues[0]['reason'] == 'no_eligible_historical_match'


def test_transfer_with_two_eligible_copies_needs_review():
    raw, review, classified = inputs()
    copy = dict(raw, calendar_event_row=2, calendar_id='new-team', event_id='new-id')
    issues = []
    result = programme_calendar([raw, copy], [classified, dict(classified, calendar_event_row=2)],
                                [review], review_issues=issues)
    assert not any(row['owner_confirmed_paid_stage'] for row in result)
    assert issues[0]['reason'] == 'multiple_eligible_matches'


def test_missing_visit_only_needs_review_from_expected_day():
    _, review, _ = inputs()
    issues = []
    assert programme_calendar([], [], [review], as_of=date(2026, 4, 3), review_issues=issues) == []
    assert issues == []
    assert programme_calendar([], [], [review], as_of=date(2026, 4, 4), review_issues=issues) == []
    assert issues[0]['reason'] == 'no_eligible_historical_match'


@pytest.mark.parametrize('changes', [
    {'warranty_claim_candidate': True},
    {'sales_record_id': 'DIFFERENT_SALE'},
])
def test_conflicting_booking_cannot_be_reclassified_as_paid(changes):
    raw, review, classified = inputs()
    result = programme_calendar([raw], [dict(classified, **changes)], [review])
    assert not result[0]['owner_confirmed_paid_stage']
