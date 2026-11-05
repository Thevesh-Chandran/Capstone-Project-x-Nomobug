from datetime import date,timedelta
import json
from webapp.predictions import booking_forecast,repeat_ranking,initial_features,rank_score,MODEL


def test_booking_forecast_uses_complete_weeks_not_future_bookings():
    monday=date(2026,10,12);events=[]
    for i,count in enumerate([10,20,30,40],1):
        events.extend({'date':(monday-timedelta(weeks=i)).isoformat()} for _ in range(count))
    initial=booking_forecast({'appointments':events},date(2026,10,15))
    more=booking_forecast({'appointments':events+[{'date':'2026-10-20'}]*200},date(2026,10,15))
    assert initial['weeks'][0]['estimate']==more['weeks'][0]['estimate']==25
    assert more['weeks'][1]['currently_booked']==200
    assert more['weeks'][1]['horizon_from_last_complete_week']==2


def test_repeat_rankings_do_not_expose_probabilities_or_include_known_repeat():
    def sale(programme):return {'date':'2026-10-01','programme_id':programme,'sales_rm':100,'package':'1x','pest':'Ants','premise':'Residential','sale_id':'X'}
    c={'name':'Example','identity_status':'reviewed','sales':[sale('A')]}
    repeated={**c,'sales':[sale('A'),sale('B')]}
    result=repeat_ranking([c,repeated],date(2026,10,15))
    assert result['eligible_customers']==1
    assert result['customers'][0]['rank']==1
    assert not any('score' in k or 'probability' in k for k in result['customers'][0])


def test_portable_model_contains_no_customer_identity_fields():
    model=json.loads(MODEL.read_text())
    assert len(model['numeric_features'])+len(model['categorical_features'])==7
    assert not any(k in model for k in ('customers','customer_key','name','phone','address'))
    features={'log_initial_sales':4,'missing_amount':0,'month_sin':0,'month_cos':1,'package':'Unknown','pest':'Unknown','premise':'Unknown'}
    assert 0<rank_score(features,model)<1


def test_stale_source_cannot_turn_partial_week_into_training_history():
    result=booking_forecast({'appointments':[]},date(2026,10,19),date(2026,10,14))
    assert result['status']=='stale_history'


def test_sunday_snapshot_does_not_establish_a_complete_week():
    result=booking_forecast({'appointments':[]},date(2026,10,19),date(2026,10,18))
    assert result['status']=='stale_history'
    result=booking_forecast({'appointments':[]},date(2026,10,19),date(2026,10,19))
    assert result['status']=='insufficient_history'
