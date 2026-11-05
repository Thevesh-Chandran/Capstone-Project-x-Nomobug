"""Paired, declared weather additions before the first visit; frozen model untouched."""
from datetime import datetime, timezone
import json
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b
from scripts import compare_callback_candidates_v2 as c
from scripts import research_callback_targets as r
from scripts.test_interservice_weather import interval_features, WEATHER

OUT=b.ROOT/'outputs/model_validation/20261017_before_first_weather'
PREVIOUS=b.ROOT/'outputs/model_validation/20261017_interservice_weather_v2'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protocol.json').exists():raise ValueError('Preserve experiment; do not overwrite')
    previous=json.loads((PREVIOUS/'protocol.json').read_text())
    assert r.digest(WEATHER)==previous['daily_weather_sha256']
    data=pd.read_pickle(PREVIOUS/'experiment_rows_private.pkl')
    facts_path=b.ROOT/previous['inputs']['facts']['path']
    assert r.digest(facts_path)==previous['inputs']['facts']['sha256']
    facts=pd.DataFrame(json.loads(facts_path.read_text()))
    facts.event_date_local=pd.to_datetime(facts.event_date_local)
    first=facts[facts.sales_record_id.isin(data.sales_record_id)&facts.event_category.eq('service')&~facts.warranty_claim_candidate.eq(True)&facts.session_total.eq(3)&facts.session_current.eq(1)]
    assert not first.sales_record_id.duplicated().any()
    first=first.set_index('sales_record_id').event_date_local.to_dict()
    locations=pd.read_json(PREVIOUS/'address_locations_private.json')
    assert r.digest(PREVIOUS/'address_locations_private.json')==previous['location_snapshot_sha256']
    locations['cell']=list(zip(locations.latitude.round(1),locations.longitude.round(1)))
    counts=locations.groupby('address_hash').cell.nunique()
    cells=locations[locations.address_hash.isin(counts[counts.eq(1)].index)].drop_duplicates('address_hash').set_index('address_hash').cell.to_dict()
    weather={}
    for line in WEATHER.read_text().splitlines():
        x=json.loads(line);d=pd.DataFrame(x['response']['daily']);d.index=pd.to_datetime(d.pop('time'))
        weather[(round(x['requested_latitude'],1),round(x['requested_longitude'],1))]=d
    extra=[];excluded=0
    for row in data.itertuples():
        end=first[row.sales_record_id];daily=weather[cells[row.address_hash]]
        item={'anchor_event_row':row.anchor_event_row};valid=True
        for days in [7,14,30]:
            values=interval_features(daily,end-pd.Timedelta(days=days),end)
            if values is None:valid=False;break
            # Fixed-duration total and daily average rainfall are equivalent. Keep total only.
            item.update({f'before_first_{days}d_'+k:v for k,v in values.items() if k!='rain_per_day_mm'})
        if valid:extra.append(item)
        else:excluded+=1
    extra=pd.DataFrame(extra);data=data.merge(extra,on='anchor_event_row',how='inner',validate='one_to_one')
    new=[x for x in extra if x!='anchor_event_row']
    baseline=previous['feature_contracts']['both_weather_sets']
    contracts={'baseline_existing_plus_between':baseline}
    contracts.update({'add_'+x:baseline+[x] for x in new})
    contracts.update({f'add_all_before_first_{days}d':baseline+[x for x in new if x.startswith(f'before_first_{days}d_')] for days in [7,14,30]})
    contracts['add_all_before_first_windows']=baseline+new
    frozen=b.ROOT/'outputs/cp2-v2/prospective_callback_v2'
    before={x.name:r.digest(x) for x in frozen.iterdir() if x.is_file()}
    protocol={'declared_at_utc':datetime.now(timezone.utc).isoformat(),'parent_protocol_sha256':r.digest(PREVIOUS/'protocol.json'),
       'parent_rows_sha256':r.digest(PREVIOUS/'experiment_rows_private.pkl'),'code_sha256':r.digest(__file__),
       'models':['et10_leaf5','lr_c1.0_plain'],'contracts':contracts,'folds':previous['folds'],'frozen_hashes':before,
       'question':previous['question'],'rules':previous['rules']+[
       'Add five weather measures separately for each of 7,14,30 days before first service, then each window together, then all windows.',
       'Same complete-weather rows for every comparison; no future daily weather and no inference of zero for missing.',
       'Fixed-window mean rainfall excluded because it is an exact rescaling of total rainfall.',
       'Exploratory input screening; no choosing inputs on these validation results and claiming independent final accuracy.',
       'Two model families fixed before fitting to test linear and nonlinear patterns; this is not a full hyperparameter search.']}
    r.write(OUT/'protocol.json',protocol)
    r.write(OUT/'coverage.json',{'parent_programmes':len(data)+excluded,'matched_programmes':len(data),'positive_programmes':int(data[b.TARGET].sum()),'missing_full_pre_first_window':excluded,'new_individual_inputs':len(new)})
    data.to_pickle(OUT/'experiment_rows_private.pkl')
    results=[];skipped=[]
    for name,start,end in protocol['folds']:
        train,test,audit=b.purged_split(data,start,end)
        try:
            if len(test)<50 or test[b.TARGET].sum()<5:raise ValueError('Insufficient outer support')
            fit,cal,inner=r.calibration_split(train)
        except ValueError as exc:
            skipped.append({'fold':name,'reason':str(exc)});continue
        for model in protocol['models']:
            for contract,numeric in contracts.items():
                features=numeric+list(b.CATEGORICAL)
                pipe=c.make_pipeline(model,numeric) if model=='et10_leaf5' else b.make_model(model,numeric)
                with threadpool_limits(limits=2):
                    pipe.fit(fit[features],fit[b.TARGET]);raw=pipe.predict_proba(cal[features])[:,1]
                    calibrator,_=b.fit_calibrator(cal[b.TARGET],raw)
                    threshold=b.select_threshold(cal[b.TARGET],b.apply_calibrator(calibrator,raw))
                    probability=b.apply_calibrator(calibrator,pipe.predict_proba(test[features])[:,1])
                tn,fp,fn,tp=confusion_matrix(test[b.TARGET],probability>=threshold,labels=[False,True]).ravel()
                result={'model':model,'features':contract,'fold':name,**b.score(test[b.TARGET],probability,threshold),
                   'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),'fit_rows':len(fit),'calibration_rows':len(cal),
                   'outer_audit':audit,'inner_audit':inner}
                results.append(result)
                with (OUT/'fold_metrics.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
            print(f'Completed {name} {model}',flush=True)
    summary=[]
    for (model,contract),g in pd.DataFrame(results).groupby(['model','features']):
        tp,fp,fn,tn=[int(g[x].sum()) for x in ['TP','FP','FN','TN']];n=tp+fp+fn+tn
        summary.append({'model':model,'features':contract,'folds':len(g),'tested':n,'returns':tp+fn,
          'accuracy':(tp+tn)/n,'recall':tp/(tp+fn),'precision':tp/(tp+fp) if tp+fp else 0,
          'f1':2*tp/(2*tp+fp+fn),'always_no_accuracy':(tn+fp)/n,'always_yes_f1':2*(tp+fn)/(n+tp+fn),
          'mean_ap':float(g.average_precision.mean()),'mean_brier':float(g.brier_score.mean()),'TP':tp,'FP':fp,'FN':fn,'TN':tn})
    assert before=={x.name:r.digest(x) for x in frozen.iterdir() if x.is_file()}
    r.write(OUT/'results.json',{'summary':summary,'skipped':skipped,'fits':len(results),'frozen_bundle_unchanged':True,'status':'adaptive_historical_development'})
    pd.DataFrame(summary).to_csv(OUT/'comparison.csv',index=False)
    print('Completed paired fits: '+str(len(results)),flush=True)

if __name__=='__main__':main()
