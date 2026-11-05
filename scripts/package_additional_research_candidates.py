"""Package reproducible research candidates; does not activate or deploy them."""
import json
import joblib
import numpy as np
import pandas as pd
from scripts.research_additional_models import ROOT,supervised,estimator,save,digest
from scripts.research_repeat_purchase import build,model


def main():
    folder=ROOT/'outputs/additional_model_research/20261014'
    repeat=json.loads((folder/'repeat90_results.json').read_text())
    source=ROOT/'outputs/business_implementation/current/customers_private.json'
    if digest(source)!=repeat['source_sha256']:raise ValueError('Research source changed; do not silently refit')
    df,_=build(json.loads(source.read_text()),'2026-10-11')
    train=df[df.outcome_end<pd.Timestamp('2026-01-01')]
    test=df[df.first_date.between(pd.Timestamp('2026-01-01'),pd.Timestamp('2026-07-13'))]
    features=['log_initial_sales','missing_amount','month_sin','month_cos','package','pest','premise']
    fitted=model(repeat['selected']['model']);fitted.fit(train[features],train.repeat90)
    saved=pd.read_csv(folder/'repeat90_test_scores.csv')
    if not np.allclose(fitted.predict_proba(test[features])[:,1],saved.probability,atol=1e-12):raise ValueError('Repeat candidate replay differs')
    joblib.dump({'status':'research_only_not_operational','model':fitted,'feature_columns':features,
        'training_label_end_before':'2026-01-01','target':'different_programme_purchase_within_90d'},folder/'repeat90_research.joblib')
    forecasts=json.loads((folder/'results.json').read_text());chosen=forecasts['weekly_bookings_h1']['selected']
    series=pd.read_csv(folder/'weekly_targets.csv',index_col=0,parse_dates=True).weekly_bookings.dropna()
    x,y=supervised(series,1);scale=max(1,float(y.mean()));fitted=estimator(chosen['model']);fitted.fit(x,y/scale)
    joblib.dump({'status':'research_challenger_not_operational','model':fitted,'target_scale':scale,'feature_count':16,
        'training_last_week_start':str(series.index[-1].date()),'target':'recorded_bookings_next_week'},folder/'booking_research_challenger.joblib')
    registry={'status':'research_candidates_not_active','original_v5_unchanged':True,'candidates':[
        {'name':'weekly_booking_baseline','method':'previous_four_complete_weeks_mean','weights_file':None,
         'status':'post_test_diagnostic_candidate_requires_forward_validation','holdout_diagnostic_mae':9.3125,
         'reason':'Simple alternative outperformed the development-selected advanced model on inspected test block'},
        {'name':'weekly_booking_challenger','method':chosen['model'],'artifact':'booking_research_challenger.joblib',
         'sha256':digest(folder/'booking_research_challenger.joblib'),'status':'research_only_not_better_than_strong_simple_baseline'},
        {'name':'repeat_purchase_90d','method':repeat['selected']['model'],'artifact':'repeat90_research.joblib',
         'sha256':digest(folder/'repeat90_research.joblib'),'status':'experimental_ranking_small_positive_sample_not_calibrated',
         'research_gate_passed':False,'replay_verified':True}],
         'deployment':'No cloud resource, live endpoint, dashboard source or automatic messaging changed'}
    save(folder/'candidate_registry.json',registry)
    print('Packaged two research estimators and one simple-method specification; repeat test replay verified; none activated.')


if __name__=='__main__':main()
