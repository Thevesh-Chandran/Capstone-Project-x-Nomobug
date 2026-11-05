"""Bounded historical horizon/target/model experiment with nested time/group splits."""
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits

from scripts import benchmark_warranty_models as b
from scripts import compare_callback_candidates_v2 as c

ROOT = b.ROOT
OUT = ROOT / 'outputs/model_validation/20261016_target_research'
PROTOCOL = ROOT / 'config/cp2_target_research_20261016.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')


def labels(frame, facts, horizon, complete):
    frame = frame.copy()
    frame['outcome_end_date'] = frame.anchor_date + pd.to_timedelta(horizon, unit='D')
    frame = frame[frame.outcome_end_date.le(complete)].copy()
    returns = {str(k): np.sort(g.event_date_local.to_numpy(dtype='datetime64[ns]'))
               for k, g in facts[facts.warranty_claim_candidate.eq(True)].groupby('sales_record_id')}
    outcome = []
    for row in frame.itertuples():
        dates = returns.get(str(row.sales_record_id), np.array([], dtype='datetime64[ns]'))
        start, end = np.datetime64(row.anchor_date), np.datetime64(row.outcome_end_date)
        outcome.append(bool(((dates > start) & (dates <= end)).any()))
    frame[b.TARGET] = outcome
    return frame


def calibration_split(train):
    dates = np.sort(train.anchor_date.unique())
    cutoff = pd.Timestamp(dates[min(len(dates)-1, int(len(dates)*.75))])
    fit, calibration, audit = b.purged_split(train, str(cutoff.date()))
    if len(fit) < 50 or len(calibration) < 30 or fit[b.TARGET].sum() < 5 or calibration[b.TARGET].sum() < 3:
        raise ValueError('Insufficient earlier fitting/calibration support')
    if fit[b.TARGET].nunique() != 2 or calibration[b.TARGET].nunique() != 2:
        raise ValueError('Both classes required')
    return fit, calibration, audit


def main():
    protocol = json.loads(PROTOCOL.read_text(encoding='utf-8'))
    for name, item in protocol['inputs'].items():
        if digest(ROOT/item['path']) != item['sha256']:
            raise ValueError('Input hash changed: '+name)
    if digest(__file__) != protocol['code_sha256']:
        raise ValueError('Code changed after declaration')
    if (OUT/'results.json').exists() or (OUT/'fold_metrics.jsonl').exists():
        raise ValueError('Preserve completed/partial run; do not overwrite')
    bundle = ROOT/'outputs/cp2-v2/prospective_callback_v2'
    before = {p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
    source = b.load_dataset_input(ROOT/protocol['inputs']['features']['path'])
    frame = c.prepare_input(source)
    anchor_keys = pd.DataFrame(json.loads((ROOT/protocol['inputs']['anchor_keys']['path']).read_text(encoding='utf-8')))
    anchor_keys.anchor_date = pd.to_datetime(anchor_keys.anchor_date)
    frame = frame.merge(anchor_keys, on=c.KEYS, how='left', validate='one_to_one')
    if frame.anchor_event_row.isna().any():
        raise ValueError('Missing archived anchor key')
    facts = pd.DataFrame(json.loads((ROOT/protocol['inputs']['facts']['path']).read_text(encoding='utf-8')))
    facts.event_date_local = pd.to_datetime(facts.event_date_local)
    if facts.calendar_event_row.duplicated().any():
        raise ValueError('Duplicate fact identities')
    linked = frame.merge(facts[['calendar_event_row','sales_record_id','event_date_local']],
        left_on='anchor_event_row',right_on='calendar_event_row',how='left',validate='many_to_one',suffixes=('','_fact'))
    if linked.calendar_event_row.isna().any() or not linked.sales_record_id.eq(linked.sales_record_id_fact).all() or not linked.anchor_date.eq(linked.event_date_local_fact if 'event_date_local_fact' in linked else linked.event_date_local).all():
        raise ValueError('Feature/fact epoch identities do not match')
    complete = pd.Timestamp(protocol['complete_through'])
    replay = labels(frame, facts, 30, complete)
    if len(replay) != len(frame) or not replay[b.TARGET].to_numpy().astype(bool).tolist() == frame[b.TARGET].to_numpy().astype(bool).tolist():
        raise ValueError('30-day labels do not reconcile; stop other horizons')
    paid = facts[facts.event_category.eq('service') & ~facts.warranty_claim_candidate.eq(True)]
    complete_programmes = set()
    for sale, group in paid.groupby('sales_record_id'):
        for n in group.session_total.dropna().unique():
            if n < 1 or int(n) != n:
                continue
            stages = group[group.session_total.eq(n) & group.session_current.between(1,n)].session_current
            if len(stages) == int(n) and set(stages) == set(range(1,int(n)+1)):
                complete_programmes.add((str(sale),int(n)))
    history = list(b.FEATURE_SETS['base'])
    service = [x for x in history if not x.startswith('prior_') and x not in ['days_since_previous_service','days_since_prior_property_claim']]
    contracts = {'service':service,'history':history,'weather':history+list(b.WEATHER_NUMERIC),
                 'environment':list(b.FEATURE_SETS['base_weather_environment'])}
    write(OUT/'data_audit.json',{'source_rows':len(frame),'source_positive_windows_30d':int(frame[b.TARGET].sum()),
        '30d_label_replay_matches':True,'matched_source_identities':len(linked),'complete_through':str(complete.date()),
        'complete_programmes':len(complete_programmes),'source_scope':'pinned archived epoch, not refreshed current business rules'})
    results, skipped, population_support = [], [], []
    combinations = list(itertools.product(protocol['horizons'],protocol['targets'],protocol['populations']))
    for horizon,target,population in combinations:
        data = labels(frame,facts,horizon,complete)
        if target == 'final_paid_service':
            data = data[data.service_number.eq(data.package_sessions_recorded)
                & pd.Series([(str(r.sales_record_id),int(r.package_sessions_recorded)) in complete_programmes
                             for r in data.itertuples()],index=data.index)]
        if population == 'residential':
            data = data[data.premise_type.eq('RESIDENTIAL')]
        population_support.append({'horizon':horizon,'target':target,'population':population,'rows':len(data),'positives':int(data[b.TARGET].sum())})
        fold_data=[]
        for name,start,end in protocol['folds']:
            train,test,audit=b.purged_split(data,start,end)
            try:
                if len(test)<50 or test[b.TARGET].sum()<5 or test[b.TARGET].nunique()!=2:
                    raise ValueError('Insufficient test support')
                fit,calibration,inner=calibration_split(train)
            except ValueError as exc:
                skipped.append({'horizon':horizon,'target':target,'population':population,'fold':name,
                                'reason':str(exc),'test_rows':len(test),'test_positives':int(test[b.TARGET].sum())})
                continue
            fold_data.append((name,fit,calibration,test,audit,inner))
        for feature_set,model in itertools.product(protocol['features'],protocol['models']):
            numeric=contracts[feature_set]; features=numeric+list(b.CATEGORICAL)
            for name,fit,calibration,test,audit,inner in fold_data:
                pipe=c.make_pipeline(model,numeric) if model=='et10_leaf5' else b.make_model(model,numeric)
                if model.startswith('rf_'):
                    pipe.named_steps['classifier'].set_params(n_jobs=2)
                with threadpool_limits(limits=2):
                    pipe.fit(fit[features],fit[b.TARGET])
                    raw_cal=pipe.predict_proba(calibration[features])[:,1]
                    calibrator,_=b.fit_calibrator(calibration[b.TARGET],raw_cal)
                    threshold=b.select_threshold(calibration[b.TARGET],b.apply_calibrator(calibrator,raw_cal))
                    probability=b.apply_calibrator(calibrator,pipe.predict_proba(test[features])[:,1])
                y=test[b.TARGET].to_numpy(dtype=bool)
                tn,fp,fn,tp=confusion_matrix(y,probability>=threshold,labels=[False,True]).ravel()
                prior=float(calibration[b.TARGET].mean())
                row={'horizon':horizon,'target':target,'population':population,'features':feature_set,'model':model,'fold':name,
                    'fit_rows':len(fit),'calibration_rows':len(calibration),'calibration_positives':int(calibration[b.TARGET].sum()),
                    **b.score(y,probability,threshold),'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),
                    'prior_baseline_brier':float(np.mean((y.astype(float)-prior)**2)),
                    'outer_split_audit':audit,'inner_split_audit':inner}
                results.append(row)
                with (OUT/'fold_metrics.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps(row,allow_nan=False)+'\n')
        print(f'Completed {horizon}d {target} {population}: rows={len(data)}, positive_windows={int(data[b.TARGET].sum())}, usable_folds={len(fold_data)}',flush=True)
    aggregate=[]
    keys=['horizon','target','population','features','model']
    if results:
        for key,g in pd.DataFrame(results).groupby(keys,sort=True):
            totals={x:int(g[x].sum()) for x in ['TP','FP','FN','TN']}
            tp,fp,fn,tn=[totals[x] for x in ['TP','FP','FN','TN']]
            aggregate.append(dict(zip(keys,key))|{'folds':len(g),'services':int(g.rows.sum()),'positive_windows':int(g.positives.sum()),
                **totals,'pooled_precision':tp/(tp+fp) if tp+fp else 0.,'pooled_recall':tp/(tp+fn),
                'pooled_f1':2*tp/(2*tp+fp+fn),'pooled_accuracy':(tp+tn)/(tp+fp+fn+tn),
                'always_no_return_accuracy':(tn+fp)/(tp+fp+fn+tn),
                'mean_ap':float(g.average_precision.mean()),'mean_brier':float(g.brier_score.mean()),
                'mean_baseline_brier':float(g.prior_baseline_brier.mean())})
    if before!={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}:
        raise ValueError('Frozen bundle changed')
    result={'status':'adaptive_historical_research_not_untouched_test','protocol_sha256':digest(PROTOCOL),
        'completed_at_utc':datetime.now(timezone.utc).isoformat(),'fits':len(results),'candidate_contracts':len(aggregate),
        'support':population_support,'skipped_folds':skipped,'summary':aggregate,'frozen_bundle_unchanged':True,'limits':protocol['limits']}
    write(OUT/'results.json',result)
    pd.DataFrame(aggregate).to_csv(OUT/'comparison.csv',index=False)
    print(json.dumps({'completed_fits':len(results),'contracts':len(aggregate),'skipped_population_folds':len(skipped)},indent=2))


if __name__=='__main__':
    main()
