import pandas as pd

from scripts.research_callback_targets import labels
from scripts import benchmark_warranty_models as b


def test_horizon_excludes_same_day_and_includes_last_day():
    frame = pd.DataFrame({'sales_record_id':['A','B','C'],
        'anchor_date':pd.to_datetime(['2025-01-01']*3)})
    facts = pd.DataFrame({'sales_record_id':['A','B','C'],
        'event_date_local':pd.to_datetime(['2025-01-01','2025-01-08','2025-01-09']),
        'warranty_claim_candidate':[True]*3})
    result = labels(frame,facts,7,pd.Timestamp('2025-02-01'))
    assert result[b.TARGET].tolist() == [False,True,False]


def test_incomplete_long_horizon_is_excluded_instead_of_negative():
    frame = pd.DataFrame({'sales_record_id':['A','B'],
        'anchor_date':pd.to_datetime(['2025-01-01','2025-02-01'])})
    facts = pd.DataFrame({'sales_record_id':['A'],
        'event_date_local':pd.to_datetime(['2025-02-15']),
        'warranty_claim_candidate':[True]})
    result = labels(frame,facts,60,pd.Timestamp('2025-03-02'))
    assert result.sales_record_id.tolist() == ['A']
    assert result[b.TARGET].tolist() == [True]


def test_only_qualifying_return_with_same_sale_changes_target():
    frame = pd.DataFrame({'sales_record_id':['A'],
        'anchor_date':pd.to_datetime(['2025-01-01'])})
    facts = pd.DataFrame({'sales_record_id':['A','B'],
        'event_date_local':pd.to_datetime(['2025-01-03','2025-01-04']),
        'warranty_claim_candidate':[False,True]})
    assert labels(frame,facts,14,pd.Timestamp('2025-02-01'))[b.TARGET].tolist() == [False]
