from datetime import datetime,timedelta,timezone
import json
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from scripts import benchmark_warranty_models as b
from scripts import freeze_callback_prospective as p
from scripts.compare_flood_models import configure_contracts


@pytest.fixture(autouse=True)
def isolated_contracts(monkeypatch):
    monkeypatch.setattr(b,'CATEGORICAL',list(b.CATEGORICAL))
    monkeypatch.setattr(b,'FEATURE_SETS',{k:list(v) for k,v in b.FEATURE_SETS.items()})
    monkeypatch.setattr(b,'FLOOD_CONTEXT_ENABLED',b.FLOOD_CONTEXT_ENABLED)
    monkeypatch.setattr(b,'REPORTED_FLOOD_CONTEXT_ENABLED',b.REPORTED_FLOOD_CONTEXT_ENABLED)


def raw_fixture():
    configure_contracts(False)
    columns=set(b.KEYS+b.BASE_NUMERIC+b.CATEGORICAL+b.WEATHER_NUMERIC+b.ENVIRONMENT_NUMERIC+b.LANDCOVER_NUMERIC)
    f=pd.DataFrame({col:[np.nan] for col in columns})
    f['population']='matched_packages_recorded_callback_30d';f['sales_record_id']='fixture'
    f['anchor_date']='2026-09-28';f['outcome_end_date']='2026-10-28'
    f['pest_category']='Lipas dan semut';f['package_category']='3x';f['premise_type']='Residential'
    f['service_number']=1;f['package_sessions_recorded']=3
    for col in ['prior_property_warranty_claims','prior_property_service_events','prior_package_warranty_claims','prior_package_service_events']:
        f[col]=0
    f['prediction_at']='2026-09-28T11:01:00+08:00'
    f['feature_snapshot_at']='2026-09-28T10:50:00+08:00'
    f['service_start_at']='2026-09-28T10:00:00+08:00'
    f['service_end_at']='2026-09-28T11:00:00+08:00'
    return f


def manifest_fixture():
    return {'frozen_at_utc':'2026-09-27T09:00:00+00:00',
      'cohort_start':'2026-09-28','cohort_end':'2026-10-27',
      'models':{'model':{'features':['anchor_is_first','anchor_is_mixed_pest']}}}


def test_predictors_do_not_require_or_retain_an_outcome():
    raw=raw_fixture().drop(columns=[b.TARGET])
    out=p.prepare_scoring_frame(raw)
    assert b.TARGET not in out
    assert out.anchor_is_mixed_pest.iloc[0]==1
    other=p.prepare_scoring_frame(raw.assign(**{b.TARGET:True}))
    pd.testing.assert_frame_equal(out,other)
    with pytest.raises(ValueError,match='missing contracted'):
        b.prepare_frame(raw)


def test_prospective_dates_require_available_snapshot_and_service_end():
    f=p.prepare_scoring_frame(raw_fixture());m=manifest_fixture()
    now=p.timestamp('2026-09-28T11:02:00+08:00')
    p.validate_prediction_times(f,m,now)
    with pytest.raises(ValueError,match='availability'):
        p.validate_prediction_times(f.assign(feature_snapshot_at='2026-09-28T11:02:00+08:00'),m,now)
    with pytest.raises(ValueError,match='service end'):
        p.validate_prediction_times(f.assign(service_end_at='2026-09-28T11:03:00+08:00'),m,now)
    with pytest.raises(ValueError,match='backfill'):
        p.validate_prediction_times(f,m,now+timedelta(minutes=5))


def test_cross_midnight_service_keeps_calendar_start_anchor():
    f=p.prepare_scoring_frame(raw_fixture()).assign(service_start_at='2026-09-28T23:00:00+08:00',
      service_end_at='2026-09-29T00:30:00+08:00',prediction_at='2026-09-29T00:31:00+08:00')
    p.validate_prediction_times(f,manifest_fixture(),p.timestamp('2026-09-29T00:32:00+08:00'))


def test_timezone_and_cohort_boundaries_are_required():
    with pytest.raises(ValueError,match='Timezone'):
        p.timestamp('2026-09-28T11:00:00')
    f=p.prepare_scoring_frame(raw_fixture()).assign(anchor_date=pd.Timestamp('2026-09-27'))
    with pytest.raises(ValueError,match='outside'):
        p.validate_prediction_times(f,manifest_fixture(),p.timestamp('2026-09-28T11:02:00+08:00'))


def test_freeze_does_not_overwrite_existing_bundle(tmp_path):
    (tmp_path/'bundle.json').write_text('{}')
    with pytest.raises(ValueError,match='already exists'):
        p.freeze(tmp_path)


def test_real_scoring_logs_unknown_outcome_and_cannot_overwrite(tmp_path,monkeypatch):
    raw=raw_fixture().drop(columns=[b.TARGET]);input_path=tmp_path/'input.json'
    input_path.write_text(raw.to_json(orient='records'))
    manifest=manifest_fixture();(tmp_path/'bundle.json').write_text(json.dumps(manifest))
    class Pipeline:
        def predict_proba(self,frame):
            assert b.TARGET not in frame
            return np.array([[.75,.25]])
    models={'model':{'features':['anchor_is_first','anchor_is_mixed_pest'],
                     'pipeline':Pipeline(),'calibrator':None}}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,models))
    fixed=p.timestamp('2026-09-28T11:02:00+08:00')
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:fixed,fromisoformat=datetime.fromisoformat))
    logs=tmp_path/'logs'
    assert p.score(tmp_path,input_path,logs)['logged_rows']==1
    record=json.loads(next(logs.glob('*.json')).read_text())
    assert record['label_status']=='awaiting_calendar_30d_outcome'
    assert b.TARGET not in record['row']
    assert record['row']['model']==.25
    with pytest.raises(ValueError,match='already logged'):
        p.score(tmp_path,input_path,logs)


def test_evaluation_waits_until_after_full_inclusive_window(tmp_path,monkeypatch):
    manifest=manifest_fixture()|{'earliest_final_evaluation_date':'2026-11-27'}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,{}))
    fixed=p.timestamp('2026-11-26T23:59:00+08:00')
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:fixed,fromisoformat=datetime.fromisoformat))
    with pytest.raises(ValueError,match='not matured'):
        p.evaluate(tmp_path,tmp_path/'missing_labels.json',tmp_path/'logs')


def test_mature_evaluation_requires_complete_resolved_calendar_labels(tmp_path,monkeypatch):
    manifest=manifest_fixture()|{'earliest_final_evaluation_date':'2026-11-27','review_fraction':.2}
    (tmp_path/'bundle.json').write_text(json.dumps(manifest))
    models={name:{'threshold':.5} for name in ['reference','challenger']}
    monkeypatch.setattr(p,'load_bundle',lambda output:(manifest,models))
    fixed=p.timestamp('2026-11-27T01:00:00+08:00')
    monkeypatch.setattr(p,'datetime',SimpleNamespace(now=lambda tz:fixed,fromisoformat=datetime.fromisoformat))
    row=json.loads(p.prepare_scoring_frame(raw_fixture().drop(columns=[b.TARGET])).to_json(orient='records',date_format='iso'))[0]
    row.update(reference=.25,challenger=.35)
    record={'logged_at_utc':'2026-09-28T11:02:00+08:00','bundle_sha256':p.digest(tmp_path/'bundle.json'),
            'row':row,'label_status':'awaiting_calendar_30d_outcome'}
    record['record_sha256']=p.record_digest(record)
    logs=tmp_path/'logs';logs.mkdir();(logs/'record.json').write_text(json.dumps(record))
    truth={k:row[k] for k in p.KEYS}|{b.TARGET:True}
    labels={'date_authority':'Calendar','cohort_complete':True,'calendar_coverage_through':'2026-11-26',
            'expected_cohort_anchors':1,'records':[truth]}
    path=tmp_path/'labels.json'
    path.write_text(json.dumps(labels|{'calendar_coverage_through':'2026-11-25'}))
    with pytest.raises(ValueError,match='incomplete'):
        p.evaluate(tmp_path,path,logs)
    path.write_text(json.dumps(labels|{'records':[truth|{b.TARGET:None}]}))
    with pytest.raises(ValueError,match='unknown is not negative'):
        p.evaluate(tmp_path,path,logs)
    path.write_text(json.dumps(labels))
    result=p.evaluate(tmp_path,path,logs)
    assert result['rows']==1
    assert result['results']['challenger']['priority_top20pct']['recall']==1
    with pytest.raises(ValueError,match='already recorded'):
        p.evaluate(tmp_path,path,logs)


def test_logged_feature_tampering_changes_integrity_digest():
    record={'row':{'service_number':1},'logged_at_utc':'2026-09-28T00:00:00Z'}
    record['record_sha256']=p.record_digest(record)
    assert record['record_sha256']==p.record_digest(record)
    record['row']['service_number']=2
    assert record['record_sha256']!=p.record_digest(record)
