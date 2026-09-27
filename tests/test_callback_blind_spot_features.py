import numpy as np
import pandas as pd
import pytest
from scripts import benchmark_warranty_models as b
from scripts.compare_callback_blind_spots import (
    add_targeted_features, training_weights, budget_alert, select_candidates,
    segment_metrics, paired_intervals, TARGETED_NUMERIC, PESTS,
)


def fixture():
    f=pd.DataFrame({'service_number':[1,2,3,1], 'package_sessions_recorded':[3,3,3,1],
      'pest_distinct_known_types':[2,2,1,1], 'normalized_pest_category':['ANT|COCKROACH','ANT|COCKROACH','COCKROACH','ANT'],
      'prior_property_warranty_claims':[0,1,2,0], 'prior_property_service_events':[0,5,8,0],
      'prior_package_warranty_claims':[0,0,1,0], 'prior_package_service_events':[0,1,2,0],
      'prior_14d_precipitation_mm':[np.nan,20,30,0], b.TARGET:[True,False,True,False]})
    for pest in PESTS:
        f[f'pest_has_{pest.lower()}']=1. if pest=='COCKROACH' else 0.
    return f


def test_stage_interactions_and_single_service_are_explicit():
    f=add_targeted_features(fixture())
    assert f.anchor_is_first.tolist()==[1,0,0,1]
    assert f.anchor_is_final.tolist()==[0,0,1,1]
    assert f.anchor_is_single_service.tolist()==[0,0,0,1]
    assert f.anchor_remaining_services.tolist()==[2,1,0,0]
    assert f.first_pest_cockroach.tolist()==[1,0,0,1]
    assert f.final_pest_cockroach.tolist()==[0,0,1,1]


def test_new_predictors_do_not_read_outcome_and_preserve_missing_weather():
    f=fixture(); first=add_targeted_features(f)
    f[b.TARGET]=~f[b.TARGET]
    second=add_targeted_features(f)
    pd.testing.assert_frame_equal(first[TARGETED_NUMERIC],second[TARGETED_NUMERIC])
    assert np.isnan(first.mixed_pest_rain_14d.iloc[0])
    assert first.prior_property_return_rate_smoothed.iloc[0]==.1


def test_focus_weights_only_emphasize_training_positive_target_rows():
    f=fixture()
    assert training_weights(f,'focus_positive_2x').tolist()==[2,1,1,1]
    assert training_weights(f,'standard').tolist()==[1,1,1,1]


def test_budget_ties_are_kept_and_invalid_scores_rejected():
    assert budget_alert([.9,.8,.8,.1,.0],.4).tolist()==[True,True,True,False,False]
    with pytest.raises(ValueError):
        budget_alert([np.nan])


def test_focus_selection_cannot_trade_away_overall_development_guards():
    base=dict(name='base__extra_trees_depth6__standard',mean_ap=.25,mean_auc=.7,
              mean_budget_recall=.5,mean_target_union_budget_recall=.1)
    low_ap=base|dict(name='low_ap',mean_ap=.24,mean_target_union_budget_recall=.9)
    low_recall=base|dict(name='low_recall',mean_budget_recall=.49,mean_target_union_budget_recall=.9)
    eligible=base|dict(name='eligible',mean_ap=.26,mean_target_union_budget_recall=.4)
    control,overall,focus=select_candidates([base,low_ap,low_recall,eligible])
    assert control==base and overall==eligible and focus==eligible
    assert select_candidates([base,low_ap,low_recall])[2]==base


def test_segment_recall_uses_global_budget_not_separate_segment_budget():
    f=fixture()
    # Only the highest-scored row fits the global 20% budget for four rows.
    result=segment_metrics(f,[.1,.9,.2,.3],.5)
    assert result['all']['budget_alerts']==1
    assert result['first_service']['budget_alerts']==0
    assert result['mixed_pest']['budget_alerts']==1


def test_post_package_anchors_cannot_enter_targeted_feature_contract():
    f=fixture(); f.loc[0,'service_number']=4
    with pytest.raises(ValueError,match='within-package'):
        add_targeted_features(f)


def test_paired_resampling_uses_aligned_cohort_and_identical_predictions_have_zero_delta():
    f=fixture().assign(population='callback',sales_record_id=['a','b','c','d'],
       anchor_date=pd.date_range('2025-01-01',periods=4),validation_group=['one','one','two','three'])
    prediction=f[['population','sales_record_id','anchor_date',b.TARGET]].assign(probability=[.8,.7,.5,.1])
    result=paired_intervals(f,prediction,prediction.iloc[::-1],30)
    assert result['groups']==3
    assert all(v==[0.,0.] for v in result['confidence_95pct'].values() if v is not None)
    changed=prediction.copy();changed.loc[0,b.TARGET]=False
    with pytest.raises(ValueError,match='outcomes differ'):
        paired_intervals(f,prediction,changed,10)
