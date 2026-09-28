import pandas as pd
import pytest
from scripts.reconcile_callback_evidence import structured_mentions, parse_service_dates, dates_within, snapshot_known_by_service_end
from scripts.compare_callback_description_features import add_description_features, comparison_partitions
from scripts import benchmark_warranty_models as b


def test_description_fields_ignore_customer_identity_and_keep_multi_pest():
    f=structured_mentions('Nama: Ant Spray\nEmail: termite@example.com\nProblem: Prevention lipas, semut dan tikus')
    assert f['problem_pests']=='ANT|COCKROACH|RODENT'
    assert f['problem_prevention_mentioned']
    assert f['method_mentions']=='UNSPECIFIED'


def test_inline_html_does_not_split_label_from_value():
    f=structured_mentions('<b>Problem:</b> Lipas &amp; semut<br><b>Method:</b> Gel bait')
    assert f['problem_pests']=='ANT|COCKROACH'
    assert f['method_mentions']=='GEL_OR_BAIT'


def test_bounded_pest_patterns_do_not_match_embedded_words():
    assert structured_mentions('Problem: tenant consult RATify')['problem_pests']=='UNSPECIFIED'


@pytest.mark.parametrize('term',['cockroach','cockroaches','roach','roaches','lipas'])
def test_cockroach_singular_plural_and_bilingual_aliases(term):
    assert structured_mentions('Problem: '+term)['problem_pests']=='COCKROACH'


def test_parse_multiple_dates_retains_review_status_for_annotations():
    assert parse_service_dates('3 Jun 2026; 14 July 2026')==(['2026-06-03','2026-07-14'],'parsed')
    assert parse_service_dates('3 Jun 2026 (rescheduled)')==(['2026-06-03'],'needs_review')
    assert parse_service_dates('31 Feb 2026')==([],'needs_review')
    assert parse_service_dates('')==([],'blank')


def test_day_first_dates_and_window_boundaries():
    assert parse_service_dates('04/03/2026')==(['2026-03-04'],'parsed')
    assert dates_within('2026-01-01',['2026-01-01','2026-01-31','2026-02-01'])==['2026-01-31']


def test_snapshot_gate_excludes_later_edits_and_unknown_timezones():
    r=dict(created_raw='2026-01-01T00:00:00Z',updated_raw='2026-01-02T00:00:00Z',end_raw='2026-01-02T08:00:00+08:00')
    assert snapshot_known_by_service_end(r)
    assert not snapshot_known_by_service_end(r|{'updated_raw':'2026-01-03T00:00:00Z'})
    assert not snapshot_known_by_service_end(r|{'created_raw':'2026-01-04T00:00:00Z'})
    assert not snapshot_known_by_service_end(r|{'end_raw':'2026-01-02'})


def test_features_require_one_to_one_frozen_keys():
    frame=pd.DataFrame([{'population':'x','sales_record_id':'1','anchor_date':pd.Timestamp('2025-01-01')}])
    features=pd.DataFrame([{'population':'x','sales_record_id':'1','anchor_date':'2025-01-01',
      'problem_pests':'ANT|COCKROACH','problem_field_present':True,'problem_prevention_mentioned':False}])
    out=add_description_features(frame,features)
    assert out.description_pest_count.iloc[0]==2
    features.sales_record_id='different'
    with pytest.raises(ValueError,match='anchors differ'):
        add_description_features(frame,features)


def test_excluded_final_rows_still_purge_their_historical_group():
    frame=pd.DataFrame({'anchor_date':pd.to_datetime(['2025-01-01','2025-02-01','2026-01-01','2026-02-01']),
      'outcome_end_date':pd.to_datetime(['2025-01-31','2025-03-03','2026-01-31','2026-03-03']),
      'validation_group':['edited-final-group','separate','edited-final-group','new'],
      'snapshot_timestamp_gate_pass':[True,True,False,True]})
    train,test,_=comparison_partitions(frame)
    assert train.validation_group.tolist()==['separate']
    assert test.validation_group.tolist()==['new']
