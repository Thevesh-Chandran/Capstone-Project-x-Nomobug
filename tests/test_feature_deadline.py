from datetime import datetime,timedelta,timezone
import pytest
from scripts.callback_live_features import query_budget

NOW=datetime(2026,10,28,12,tzinfo=timezone.utc)

def test_feature_query_uses_remaining_time_inside_the_existing_gate():
    assert query_budget(NOW+timedelta(seconds=12),now=NOW)==12

def test_feature_query_caps_each_wait_instead_of_waiting_five_minutes():
    assert query_budget(NOW+timedelta(minutes=4),now=NOW)==60

@pytest.mark.parametrize('seconds',[0,-1,-300])
def test_expired_feature_work_fails_instead_of_claiming_a_timely_prediction(seconds):
    with pytest.raises(TimeoutError):query_budget(NOW+timedelta(seconds=seconds),now=NOW)

def test_non_collection_replay_keeps_its_original_timeout():
    assert query_budget(None,now=NOW)==300
