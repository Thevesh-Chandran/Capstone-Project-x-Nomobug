import pandas as pd
from scripts.test_compact_notes_rain import available_notes,make_model

def test_missing_late_and_mismatched_notes_remain_unknown():
    f=pd.DataFrame({'anchor_event_row':[1,2,3,999],'anchor_date':pd.to_datetime(['2025-01-01']*4)})
    raw=pd.DataFrame([{'calendar_event_row':i,'start_raw':start,'end_raw':'2025-01-01T04:00:00Z','created_raw':'2024-12-01T00:00:00Z',
        'updated_raw':updated,'description':'Problem: masih banyak lipas'} for i,start,updated in [
        (1,'2025-01-01T02:00:00Z','2024-12-31T00:00:00Z'),
        (2,'2025-01-01T02:00:00Z','2025-01-02T00:00:00Z'),
        (3,'2025-01-02T02:00:00Z','2024-12-31T00:00:00Z')]])
    result=available_notes(f,raw)
    assert result.notes_unknown.tolist()==[0,1,1,1]
    assert result.heavy_pest_mention.iloc[0]==1 and result.pest_persisting_mention.iloc[0]==1
    assert result.heavy_pest_mention.iloc[1:].isna().all()

def test_compact_transformer_uses_declared_columns_only(monkeypatch):
    # prepare_input config adds the premise/normalized categorical context.
    from scripts import compare_callback_candidates_v2 as c
    from scripts import benchmark_warranty_models as benchmark
    import copy
    for name in ['CATEGORICAL','FEATURE_SETS','FLOOD_CONTEXT_ENABLED','REPORTED_FLOOD_CONTEXT_ENABLED']:
        monkeypatch.setattr(benchmark,name,copy.deepcopy(getattr(benchmark,name)))
    c.configure_contracts(False)
    for family in ['Extra Trees','Random Forest']:
        p=make_model(family,['service_number','normalized_pest_category','premise_type'])
        fields=[x for _,_,cols in p.steps[0][1].transformers for x in cols]
        assert set(fields)=={'service_number','normalized_pest_category','premise_type'}
