from copy import deepcopy
from scripts.reconcile_collection_candidates import reconcile
from scripts.cp2_pipeline_tick import event_key


def test_current_reconstruction_never_rewrites_original_missing_prediction():
    event={'calendar_id':'team','event_id':'one','calendar_event_row':1,'status':'confirmed',
        'start_raw':'2026-10-15T10:00:00+08:00','end_raw':'2026-10-15T11:00:00+08:00','summary':'GPC 1/3 Example'}
    key=event_key(event)
    history={'missed':{key:'2026-10-15T03:06:00Z'},'missed_anchor_dates':{key:'2026-10-15'}}
    original=deepcopy(history)
    result=reconcile(history,{'records':[event]},{'records':[event]},
        [{'calendar_event_row':1,'population_reason':'candidate'}],[{'anchor_event_row':1}],
        '2026-10-10','2026-10-30')
    assert result['current_reconstruction_counts']=={'currently_eligible_anchor':1}
    assert result['reviews'][0]['original_decision']=='not_yet_classified'
    assert history==original and result['reviews'][0]['original_missed_at']==original['missed'][key]


def test_rescheduled_key_stays_a_missing_original_key():
    old={'calendar_id':'team','event_id':'one','calendar_event_row':1,
        'start_raw':'2026-10-15T10:00:00+08:00','end_raw':'2026-10-15T11:00:00+08:00'}
    current={**old,'start_raw':'2026-10-16T10:00:00+08:00','end_raw':'2026-10-16T11:00:00+08:00'}
    key=event_key(old)
    history={'missed':{key:'2026-10-15T03:06:00Z'},'missed_anchor_dates':{key:'2026-10-15'}}
    result=reconcile(history,{'records':[current]},{'records':[old]},[],[],'2026-10-10','2026-10-30')
    assert result['current_reconstruction_counts']=={'current_calendar_key_missing':1}
