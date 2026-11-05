from datetime import datetime, timezone
import hashlib

from scripts import calendar_appointment_policy as policy
from scripts import cp2_pipeline_tick as tick


def example():
    return {'calendar_id': 'calendar', 'event_id': 'example', 'status': 'confirmed',
            'summary': 'GPC 2/3 Example', 'is_all_day': False,
            'start_raw': '2026-10-04T15:00:00+08:00',
            'end_raw': '2026-10-04T16:00:00+08:00'}


def review(event):
    return {'event_identity_hash': hashlib.sha256(
        f"{event['calendar_id']}|{event['event_id']}".encode()).hexdigest(),
        'expected_start_at_utc': '2026-10-04T07:00:00+00:00',
        'expected_end_at_utc': '2026-10-04T08:00:00+00:00'}


def test_real_sunday_service_remains_eligible():
    event = example()
    assert policy.utc(event['start_raw']).weekday() == 6
    assert tick.service_window(event) == (
        datetime(2026, 10, 4, 7, tzinfo=timezone.utc),
        datetime(2026, 10, 4, 8, tzinfo=timezone.utc))


def test_only_exact_reviewed_identity_and_window_are_parked(monkeypatch):
    event = example()
    reviews = [review(event)]
    monkeypatch.setattr(policy, 'load_policy', lambda: reviews)
    assert tick.service_window(event) is None
    assert not policy.is_confirmed_placeholder(dict(event, event_id='other'))
    assert not policy.is_confirmed_placeholder(dict(event, calendar_id='other'))
    assert not policy.is_confirmed_placeholder(dict(event, end_raw='2026-10-04T17:00:00+08:00'))


def test_review_expires_when_moved_to_an_agreed_date_including_sunday(monkeypatch):
    event = example()
    monkeypatch.setattr(policy, 'load_policy', lambda: [review(event)])
    moved = dict(event, start_raw='2026-10-11T15:00:00+08:00',
                 end_raw='2026-10-11T16:00:00+08:00')
    assert tick.service_window(moved) is not None


def test_shipped_policy_has_one_owner_confirmed_exact_window():
    rows = policy.load_policy()
    assert len(rows) == 1
    assert rows[0]['appointment_state'] == 'awaiting_client_date'
    assert len(policy.policy_sha256()) == 64
