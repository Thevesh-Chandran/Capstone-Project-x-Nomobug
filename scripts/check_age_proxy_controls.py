"""Negative controls after initial age comparison; exploratory, not a new test."""
import json
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from scripts.test_age_holiday_predictors import OUT,ROOT,AGE,age_at_locations
from scripts.research_expanded_targets import save,sha
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.research_callback_targets import calibration_split

def main():
    assert not (OUT/'control_protocol.json').exists()
    save(OUT/'control_protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'reason':'Age passed initial two-period AP/Brier screen; determine whether availability/geocode precision or age codes carry signal. This follow-up was declared after seeing that result.',
        'controls':'Availability flag alone; five fixed permutations of age codes among accepted unique addresses, preserving exact missingness. Test same two periods; not independent confirmation.',
        'limitations':'Permutation preserves known locations, so cannot prove availability independent of customer/source selection. Small coverage, repeated data inspection and tree feature-subsampling variation remain.'})
    f=c.prepare_input(b.load_dataset_input(ROOT/'outputs/cp2-v2/source_refresh_20260927/refreshed/dataset_input.json'));f=f[f.anchor_date<'2026-01-01'].copy()
    matches=pd.read_csv(OUT/'age_matches_private.csv');mapping=dict(zip(matches.address_hash,matches.settlement_age_code))
    f['settlement_age_code']=f.address_hash.map(mapping).where(f.location_uncertainty_radius_m.le(250));f['settlement_age_unknown']=f.settlement_age_code.isna().astype(int)
    features=json.loads((ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json').read_text())['models']['challenger_all_history']['features']
    rows=[]
    for period,start,end in [x for x in b.DEVELOPMENT_FOLDS if x[1]>='2025-07-01']:
        for seed in [-1,0,1,2,3,4]:
            g=f.copy();extra=['settlement_age_unknown'] if seed==-1 else AGE
            if seed>=0:
                rng=np.random.default_rng(20261018+seed);shuffled=dict(zip(matches.address_hash,rng.permutation(matches.settlement_age_code.to_numpy())))
                g['settlement_age_code']=g.address_hash.map(shuffled).where(g.location_uncertainty_radius_m.le(250))
                assert g.settlement_age_code.isna().equals(f.settlement_age_code.isna())
            train,test,_=b.purged_split(g,start,end);fit,cal,_=calibration_split(train);cols=features+[x for x in extra if fit[x].nunique(dropna=True)>1]
            pipe=c.make_pipeline('et10_leaf5',[x for x in cols if x not in b.CATEGORICAL])
            with threadpool_limits(limits=2):
                pipe.fit(fit[cols],fit[b.TARGET],classifier__sample_weight=c.training_weights(fit,'standard'))
                cc,_=b.fit_calibrator(cal[b.TARGET],pipe.predict_proba(cal[cols])[:,1]);cut=b.select_threshold(cal[b.TARGET],b.apply_calibrator(cc,pipe.predict_proba(cal[cols])[:,1]))
                met=b.score(test[b.TARGET],b.apply_calibrator(cc,pipe.predict_proba(test[cols])[:,1]),cut)
            rows.append({'period':period,'control':'Known location only' if seed==-1 else f'Shuffled age {seed}','inputs':len(cols),**met})
            pd.DataFrame(rows).to_csv(OUT/'age_control_metrics.csv',index=False)
    d=pd.DataFrame(rows);actual=pd.read_csv(OUT/'fold_metrics.csv');real=actual[actual.variant.eq('Settlement age proxy')].set_index('period')
    base=actual[actual.variant.eq('Existing inputs')].set_index('period');details=[]
    for name,part in d.groupby('control',sort=False):
        part=part.set_index('period');details.append({'control':name,'mean_ap':float(part.average_precision.mean()),'mean_brier':float(part.brier_score.mean()),
            'beats_baseline_both_periods':bool(((part.average_precision>base.average_precision)&(part.brier_score<base.brier_score)).all()),
            'real_age_better_both_measures_in_periods':int(((real.average_precision>part.average_precision)&(real.brier_score<part.brier_score)).sum())})
    save(OUT/'control_results.json',{'fits':len(rows),'controls':details,'interpretation':'Exploratory controls; no significance claim or model promotion.'});print(json.dumps(details))

if __name__=='__main__':main()
