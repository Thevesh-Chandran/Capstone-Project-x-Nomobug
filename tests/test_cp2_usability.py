import pytest
from scripts.summarize_cp2_usability import summarize


def test_blank_tasks_are_not_a_success_claim():
    result = summarize([{'task_id':'reminders'}])
    assert result['status'] == 'not_tested'
    assert result['success_share'] is None and result['median_seconds'] is None


def test_observed_attempt_and_duplicate_guard():
    row = dict(participant_code='P1', task_id='model_tradeoff',
        started_at='2026-10-11T14:00:00+08:00', finished_at='2026-10-11T14:01:00+08:00',
        answer='4 found; 16 selected without callback; 1 missed', correct='yes', help_needed='no')
    assert summarize([row])['median_seconds'] == 60
    with pytest.raises(ValueError, match='unique'):
        summarize([row, row])
