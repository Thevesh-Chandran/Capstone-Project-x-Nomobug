"""Paired historical 3x-final-service experiment. Does not modify any live model."""
from datetime import datetime, timezone
import json
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b
from scripts import compare_callback_candidates_v2 as c
from scripts import research_callback_targets as r

OUT = b.ROOT/'outputs/model_validation/20261017_interservice_weather_v2'
WEATHER = b.ROOT/'data/processed/weather/open_meteo_ifs_grid_2023_2026_v3.jsonl'


def interval_features(daily, start, end):
    """[earlier service date, later service date): excludes unfinished anchor day."""
    days = (end-start).days
    if days <= 0:
        raise ValueError('Service stages must have strictly increasing dates')
    part = daily.loc[(daily.index >= start) & (daily.index < end)]
    fields = ['precipitation_sum','temperature_2m_mean','relative_humidity_2m_mean',
              'soil_moisture_0_to_7cm_mean']
    if len(part) != days or part[fields].isna().any().any():
        return None
    rain = part.precipitation_sum
    return {'rain_total_mm':float(rain.sum()), 'rain_per_day_mm':float(rain.mean()),
            'heavy_rain_days_10mm':int(rain.ge(10).sum()),
            'temperature_mean_c':float(part.temperature_2m_mean.mean()),
            'humidity_mean_pct':float(part.relative_humidity_2m_mean.mean()),
            'soil_moisture_mean':float(part.soil_moisture_0_to_7cm_mean.mean())}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT/'protocol.json').exists():
        raise ValueError('Preserve declared experiment; use a separate output for reruns')
    protocol=json.loads((b.ROOT/'config/cp2_3x_final_target_research_20261017.json').read_text())
    for name,item in protocol['inputs'].items():
        assert r.digest(b.ROOT/item['path']) == item['sha256'], name
    frozen=b.ROOT/'outputs/cp2-v2/prospective_callback_v2'
    before={p.name:r.digest(p) for p in frozen.iterdir() if p.is_file()}
    frame=c.prepare_input(b.load_dataset_input(b.ROOT/protocol['inputs']['features']['path']))
    keys=pd.DataFrame(json.loads((b.ROOT/protocol['inputs']['anchor_keys']['path']).read_text()))
    keys.anchor_date=pd.to_datetime(keys.anchor_date)
    frame=frame.merge(keys,on=c.KEYS,how='left',validate='one_to_one')
    assert frame.anchor_event_row.notna().all()
    facts=pd.DataFrame(json.loads((b.ROOT/protocol['inputs']['facts']['path']).read_text()))
    facts.event_date_local=pd.to_datetime(facts.event_date_local)
    assert not facts.calendar_event_row.duplicated().any()
    linked=frame.merge(facts[['calendar_event_row','sales_record_id','event_date_local']],left_on='anchor_event_row',right_on='calendar_event_row',suffixes=('','_fact'),validate='many_to_one')
    assert linked.sales_record_id.eq(linked.sales_record_id_fact).all()
    assert linked.anchor_date.eq(linked.event_date_local).all()
    replay=r.labels(frame,facts,30,pd.Timestamp(protocol['complete_through']))
    assert len(replay)==len(frame) and replay[b.TARGET].astype(bool).tolist()==frame[b.TARGET].astype(bool).tolist()
    # Hash-based address identity, never mixed Calendar row numbers from different snapshots.
    from google.cloud import bigquery
    client=bigquery.Client(project='profound-keel-500007-s4',location='asia-southeast1')
    sql='SELECT DISTINCT address_hash, latitude, longitude FROM `profound-keel-500007-s4.quality.calendar_event_geocodes_all_v2`'
    dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False))
    assert dry.total_bytes_processed <= 100*1024*1024
    locations=pd.DataFrame([dict(x) for x in client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100*1024*1024)).result()]);client.close()
    locations.to_json(OUT/'address_locations_private.json',orient='records')
    # Exclude an address if conflicting coordinates map it to different weather cells.
    locations['cell']=list(zip(locations.latitude.round(1),locations.longitude.round(1)))
    unambiguous=locations.groupby('address_hash').cell.nunique().eq(1)
    cell_by_address=locations[locations.address_hash.isin(unambiguous[unambiguous].index)].drop_duplicates('address_hash').set_index('address_hash').cell.to_dict()
    weather={}
    for line in WEATHER.read_text().splitlines():
        item=json.loads(line);d=pd.DataFrame(item['response']['daily']);d.index=pd.to_datetime(d.pop('time'))
        weather[(round(item['requested_latitude'],1),round(item['requested_longitude'],1))]=d
    paid=facts[facts.event_category.eq('service') & ~facts.warranty_claim_candidate.eq(True)]
    stage_dates={}
    for sale,g in paid.groupby('sales_record_id'):
        g=g[g.session_total.eq(3)&g.session_current.between(1,3)]
        if len(g)==3 and set(g.session_current)=={1,2,3}:
            dates=g.sort_values('session_current').event_date_local.tolist()
            if dates[0]<dates[1]<dates[2]:stage_dates[str(sale)]=dates
    final=frame[frame.service_number.eq(3)&frame.sales_record_id.astype(str).isin(stage_dates)].copy()
    address_counts=frame.groupby('sales_record_id').address_hash.nunique(dropna=False)
    conflicting=address_counts[address_counts.ne(1)].index
    conflict_count=int(final.sales_record_id.isin(conflicting).sum())
    final=final[~final.sales_record_id.isin(conflicting)].copy()
    additions=[]; exclusions={'multiple_programme_addresses':conflict_count,'no_unambiguous_weather_cell':0,'incomplete_daily_weather':0,'archived_weather_replay_mismatch':0}
    for row in final.itertuples():
        dates=stage_dates[str(row.sales_record_id)]
        assert dates[2]==row.anchor_date
        daily=weather.get(cell_by_address.get(row.address_hash))
        if daily is None:
            exclusions['no_unambiguous_weather_cell']+=1;continue
        prior=daily.loc[(daily.index>=row.anchor_date-pd.Timedelta(days=7))&(daily.index<row.anchor_date)]
        if len(prior)!=7 or not np.isclose(prior.precipitation_sum.sum(),row.prior_7d_precipitation_mm,atol=1e-6):
            exclusions['archived_weather_replay_mismatch']+=1;continue
        values={'anchor_event_row':row.anchor_event_row}
        valid=True
        for prefix,start,end in [('first_to_second',dates[0],dates[1]),('second_to_third',dates[1],dates[2])]:
            result=interval_features(daily,start,end)
            if result is None:valid=False;break
            values[prefix+'_days']=(end-start).days
            values.update({prefix+'_'+key:value for key,value in result.items()})
        if valid:additions.append(values)
        else:exclusions['incomplete_daily_weather']+=1
    extra=pd.DataFrame(additions)
    data=final.merge(extra,on='anchor_event_row',how='inner',validate='one_to_one')
    data.to_pickle(OUT/'experiment_rows_private.pkl')
    duration=[x for x in extra if x.endswith('_days')]
    interval=[x for x in extra if x not in ['anchor_event_row']+duration]
    base=list(b.FEATURE_SETS['base'])+duration
    contracts={'history_and_gap_lengths':base,
               'existing_pre_service_weather':base+list(b.WEATHER_NUMERIC),
               'between_service_weather':base+interval,
               'both_weather_sets':base+list(b.WEATHER_NUMERIC)+interval}
    declaration={'declared_at_utc':datetime.now(timezone.utc).isoformat(),'question':'Recorded pest-related return within 30 days after residential third paid service',
      'inputs':protocol['inputs'],'daily_weather_sha256':r.digest(WEATHER),'location_snapshot_sha256':r.digest(OUT/'address_locations_private.json'),
      'code_sha256':r.digest(__file__),'frozen_hashes':before,'folds':protocol['folds'],'models':protocol['models'],'feature_contracts':contracts,
      'rules':['Identical complete-weather rows for every comparison; both gap lengths in every baseline.',
        'Exclude multiple-address programmes; seven-day rain must reproduce the archived feature to validate the weather-cell join.',
        'Intervals include earlier service day and exclude later service day; no actual weather on/after third service.',
        'Exact unique recorded stages 1,2,3 and strictly increasing dates; no arbitrary 14-day eligibility cutoff.',
        'Outer chronological property/sale-purged folds; calibration and F1 threshold only from earlier data.',
        'Historical reanalysis, not archived real-time weather availability: retrospective development evidence only.',
        'Current hash-matched geocodes joined to archived address identities; location history not independently verified.',
        'Flood events/water levels omitted: cached anchor summaries do not verify daily interval observations.',
        'No live/frozen model changes and no selecting split to inflate accuracy.']}
    r.write(OUT/'protocol.json',declaration)
    r.write(OUT/'coverage.json',{'residential_3x_source_service_windows':len(frame),'complete_final_programmes':len(final),'matched_weather_programmes':len(data),'positive_programmes':int(data[b.TARGET].sum()),'excluded':exclusions})
    results=[];skipped=[]
    for name,start,end in protocol['folds']:
        train,test,audit=b.purged_split(data,start,end)
        try:
            if len(test)<50 or test[b.TARGET].sum()<5 or test[b.TARGET].nunique()!=2:raise ValueError('Insufficient outer test support')
            fit,cal,inner=r.calibration_split(train)
        except ValueError as exc:
            skipped.append({'fold':name,'reason':str(exc),'rows':len(test),'positives':int(test[b.TARGET].sum())});continue
        for model in protocol['models']:
            for contract,numeric in contracts.items():
                features=numeric+list(b.CATEGORICAL)
                pipe=c.make_pipeline(model,numeric) if model=='et10_leaf5' else b.make_model(model,numeric)
                if model.startswith('rf_'):pipe.named_steps['classifier'].set_params(n_jobs=2)
                with threadpool_limits(limits=2):
                    pipe.fit(fit[features],fit[b.TARGET]);raw=pipe.predict_proba(cal[features])[:,1]
                    calibrator,_=b.fit_calibrator(cal[b.TARGET],raw)
                    threshold=b.select_threshold(cal[b.TARGET],b.apply_calibrator(calibrator,raw))
                    probability=b.apply_calibrator(calibrator,pipe.predict_proba(test[features])[:,1])
                tn,fp,fn,tp=confusion_matrix(test[b.TARGET],probability>=threshold,labels=[False,True]).ravel()
                result={'model':model,'features':contract,'fold':name,**b.score(test[b.TARGET],probability,threshold),
                        'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),'fit_rows':len(fit),'calibration_rows':len(cal),'outer_audit':audit,'inner_audit':inner}
                results.append(result)
                with (OUT/'fold_metrics.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
        print('Completed '+name,flush=True)
    summary=[]
    for (model,contract),g in pd.DataFrame(results).groupby(['model','features']):
        tp,fp,fn,tn=[int(g[x].sum()) for x in ['TP','FP','FN','TN']];n=tp+fp+fn+tn
        summary.append({'model':model,'features':contract,'folds':len(g),'tested':n,'returns':tp+fn,
            'accuracy':(tp+tn)/n,'recall':tp/(tp+fn),'precision':tp/(tp+fp) if tp+fp else 0,
            'f1':2*tp/(2*tp+fp+fn),'always_no_accuracy':(tn+fp)/n,'mean_ap':float(g.average_precision.mean()),
            'mean_brier':float(g.brier_score.mean()),'TP':tp,'FP':fp,'FN':fn,'TN':tn})
    assert before=={p.name:r.digest(p) for p in frozen.iterdir() if p.is_file()}
    r.write(OUT/'results.json',{'summary':summary,'skipped':skipped,'frozen_bundle_unchanged':True,'fits':len(results),'status':'adaptive_historical_development'})
    pd.DataFrame(summary).to_csv(OUT/'comparison.csv',index=False)
    print(pd.DataFrame(summary).to_string(index=False))

if __name__=='__main__':main()
