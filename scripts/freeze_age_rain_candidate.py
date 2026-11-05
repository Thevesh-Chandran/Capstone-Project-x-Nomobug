"""Separate four-way frozen historical comparison, preserving original artifacts."""
from pathlib import Path
from datetime import datetime,timezone
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits
import nbformat
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.evaluate_larger_frozen_model import make_partitions,bootstrap_intervals
from scripts.test_age_holiday_predictors import age_at_locations
from scripts.test_interservice_weather import WEATHER
from scripts.research_expanded_targets import ROOT,save,sha
from scripts.build_supervisor_model_review import execute,export_html

OUT=ROOT/'outputs/model_validation/20261018_frozen_age_rain'
ORIGINAL=ROOT/'outputs/cp2-v2/prospective_callback_v2'
RAIN=['previous_interval_rain_mean_mm','since_first_visit_rain_mean_mm','previous_interval_days','interval_rain_unknown','before_first_7d_rain_mean_mm','before_first_30d_rain_mean_mm']
AGE=['settlement_age_code','settlement_age_unknown']

def rainfall_additions(f,locations,weather):
    locations=locations.copy();locations['cell']=list(zip(locations.latitude.round(1),locations.longitude.round(1)))
    valid=locations.groupby('address_hash').cell.nunique().eq(1);mapping=locations[locations.address_hash.isin(valid[valid].index)].drop_duplicates('address_hash').set_index('address_hash').cell.to_dict()
    result=[]
    for _,part in f.groupby(['sales_record_id','address_hash'],dropna=False):
        for idx,row in part.iterrows():
            v={name:np.nan for name in RAIN};v['interval_rain_unknown']=1
            daily=weather.get(mapping.get(row.address_hash));stage=row.service_number
            if daily is not None:
                prior7=daily[(daily.index>=row.anchor_date-pd.Timedelta(days=7))&(daily.index<row.anchor_date)].precipitation_sum
                # Confirm this address resolves to the same weather cell as the frozen data.
                if len(prior7)!=7 or not np.isclose(prior7.sum(),row.prior_7d_precipitation_mm,atol=1e-6):daily=None
            if daily is not None:
                past=part[(part.anchor_date<row.anchor_date)&(part.service_number<stage)]
                first=past[past.service_number.eq(1)] if stage>1 else part.loc[[idx]]
                if len(first)==1:
                    start=first.anchor_date.iloc[0]
                    for days in [7,30]:
                        p=daily[(daily.index>=start-pd.Timedelta(days=days))&(daily.index<start)].precipitation_sum
                        if len(p)==days and p.notna().all():v[f'before_first_{days}d_rain_mean_mm']=float(p.mean())
                previous=past[past.service_number.eq(stage-1)]
                if stage>1 and len(previous)==1:
                    start=previous.anchor_date.iloc[0];length=(row.anchor_date-start).days
                    p=daily[(daily.index>=start)&(daily.index<row.anchor_date)].precipitation_sum
                    if length>0 and len(p)==length and p.notna().all():
                        v.update(previous_interval_rain_mean_mm=float(p.mean()),previous_interval_days=length,interval_rain_unknown=0)
                    if len(first)==1:
                        start=first.anchor_date.iloc[0];p=daily[(daily.index>=start)&(daily.index<row.anchor_date)].precipitation_sum
                        if len(p)==(row.anchor_date-start).days and len(p)>0 and p.notna().all():v['since_first_visit_rain_mean_mm']=float(p.mean())
            result.append({'index':idx,**v})
    return pd.DataFrame(result).set_index('index').reindex(f.index)

def main():
    OUT.mkdir(parents=True,exist_ok=True);assert not (OUT/'protocol.json').exists(),'Preserve completed/declaration artifacts'
    original={p.name:sha(p) for p in ORIGINAL.iterdir() if p.is_file()}
    bundle=json.loads((ORIGINAL/'bundle.json').read_text());source=ROOT/bundle['training_input_relative_path'];old=joblib.load(ORIGINAL/'challenger_all_history.joblib');base=old['members'][0]['features']
    variants={'baseline':[],'age':AGE,'rain':RAIN,'age_and_rain':AGE+RAIN}
    save(OUT/'protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(source),'original_hashes':original,'script_sha256':sha(__file__),
        'question':'Recorded pest-related return within30days after paid service','variants':variants,'baseline_inputs':base,
        'partition':'Same fixed property/package-disjoint partition as larger historical study: train Mar2024-May2025; validate Jul-Nov2025; assess Jan-Aug2026. Outcome maturity gaps retained.',
        'rules':'Clone original ExtraTrees settings; fit on training only; calibrate/select threshold only on validation. Save all four artifacts and hashes before any assessment prediction. No test-based winner or threshold tuning.',
        'rain_timing':'Original pre-anchor rain retained. Add mean rain between immediately preceding numbered eligible paid visit and anchor, since first known visit, and prior7/30day means before first visit. Only same frozen sale/address, unique earlier stages; no future day used. First visits/ambiguous gaps remain unknown.',
        'age_timing':'GHS-AGE released June26 2025, before validation begins; reconstruct earlier training context from2020 map. Nine spatial checks, uncertainty<=250m.',
        'limits':'Historical records and assessment period previously inspected in other experiments. Separately frozen research comparison, not new independent prospective evidence. Missing interval may reflect ineligible/missing prior service; frozen sale links are not rebuilt from current sources. Historical weather revisions/geocodes retrospective.'})
    f=c.prepare_input(b.load_dataset_input(source));locations=pd.DataFrame(json.loads((ROOT/'outputs/model_validation/20261017_interservice_weather_v2/address_locations_private.json').read_text()))
    weather={}
    for line in WEATHER.read_text().splitlines():
        item=json.loads(line);d=pd.DataFrame(item['response']['daily']);d.index=pd.to_datetime(d.pop('time'));weather[(round(item['requested_latitude'],1),round(item['requested_longitude'],1))]=d
    f=f.join(rainfall_additions(f,locations,weather))
    eligible=set(f.loc[f.location_uncertainty_radius_m.le(250),'address_hash']);raster=next((ROOT/'outputs/model_validation/20261018_age_holidays').glob('*.tif'))
    codes,_=age_at_locations(locations[locations.address_hash.isin(eligible)],raster)
    f['settlement_age_code']=f.address_hash.map(codes).where(f.location_uncertainty_radius_m.le(250));f['settlement_age_unknown']=f.settlement_age_code.isna().astype(int)
    train,val,test=make_partitions(f);assert (len(train),len(val),len(test))==(1506,1177,2075)
    coverage=[]
    for name,part in [('Training',train),('Validation',val),('Assessment',test)]:
        coverage.append({'Partition':name,'Services':len(part),'Returns':int(part[b.TARGET].sum()),'Known age':int(part.settlement_age_code.notna().sum()),
            'Known previous interval rainfall':int(part.previous_interval_rain_mean_mm.notna().sum()),'Known before-first rainfall':int(part.before_first_7d_rain_mean_mm.notna().sum())})
    save(OUT/'coverage.json',coverage);f[c.KEYS+RAIN+AGE].to_pickle(OUT/'new_inputs_private.pkl')
    # Clone the original preprocessor exactly, extending only its numeric column list.
    manifest={}
    for name,extra in variants.items():
        cols=base+extra;pipe=clone(old['members'][0]['pipeline']);pipe.named_steps['classifier'].set_params(n_jobs=2)
        pre=pipe.named_steps['preprocess'] if 'preprocess' in pipe.named_steps else pipe.steps[0][1]
        transformers=[]
        for key,transformer,columns in pre.transformers:
            columns=list(columns)
            if set(columns)&set(b.CATEGORICAL):pass
            else:columns=columns+extra
            transformers.append((key,transformer,columns))
        pre.set_params(transformers=transformers)
        with threadpool_limits(limits=2):
            pipe.fit(train[cols],train[b.TARGET],classifier__sample_weight=np.ones(len(train)))
            raw=pipe.predict_proba(val[cols])[:,1];cal,_=b.fit_calibrator(val[b.TARGET],raw);threshold=b.select_threshold(val[b.TARGET],b.apply_calibrator(cal,raw))
        artifact={'pipeline':pipe,'features':cols,'calibrator':cal,'threshold':threshold,'variant':name,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha(OUT/'protocol.json')}
        path=OUT/f'{name}.joblib';joblib.dump(artifact,path);manifest[name]={'sha256':sha(path),'threshold':threshold,'inputs':len(cols),'frozen_at_utc':artifact['frozen_at_utc']}
    save(OUT/'frozen_manifest.json',{'models':manifest,'all_frozen_before_assessment':True,'protocol_sha256':sha(OUT/'protocol.json')})
    results=[]
    for name,receipt in manifest.items():
        path=OUT/f'{name}.joblib';assert sha(path)==receipt['sha256'];m=joblib.load(path)
        with threadpool_limits(limits=2):p=b.apply_calibrator(m['calibrator'],m['pipeline'].predict_proba(test[m['features']])[:,1])
        metrics=b.score(test[b.TARGET],p,m['threshold']);tn,fp,fn,tp=confusion_matrix(test[b.TARGET],p>=m['threshold'],labels=[False,True]).ravel()
        results.append({'variant':name,'inputs':len(m['features']),'threshold':m['threshold'],'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),**metrics,
            'intervals':bootstrap_intervals(test,p,m['threshold'])})
        pd.DataFrame({'actual':test[b.TARGET].to_numpy(),'probability':p}).to_csv(OUT/f'{name}_assessment.csv',index=False)
        save(OUT/'results.json',results);print(name,json.dumps(metrics),flush=True)
    assert original=={p.name:sha(p) for p in ORIGINAL.iterdir() if p.is_file()}
    previous=json.loads((ROOT/'outputs/model_validation/20261017_larger_frozen_test/results.json').read_text());assert np.isclose(results[0]['precision'],previous['metrics']['precision'])
    save(OUT/'acceptance.json',{'original_frozen_unchanged':True,'baseline_reproduces_previous_precision':True,'all_models_frozen_before_assessment':True,'assessment_rows':len(test),'source_hash':sha(source)})
    report(results,coverage)

def report(results,coverage):
    table=[{'Model':r['variant'],'Inputs':r['inputs'],'Accuracy %':round(100*r['accuracy'],2),'Precision %':round(100*r['precision'],2),'Recall %':round(100*r['recall'],2),'F1':r['f1'],'Correct alerts':r['TP'],'False alerts':r['FP'],'Missed returns':r['FN']} for r in results]
    cells=[nbformat.v4.new_markdown_cell('''# Separate frozen test: neighbourhood age and rainfall
**Same 30-day return target, same model settings, same 2,075 later assessment services.**

Four separate candidates were fitted and frozen before any assessment predictions: original93inputs; add age; add rainfall; add both. The live frozen model remains separate.

## Rainfall timing
The original inputs already include rain before the service. The added inputs include rain before the first known visit and average rain between earlier visits, ending before the prediction service date. No rain occurring after prediction was included. First visits have no between-visit interval and remain unknown for that input.

## Partitions
Training: March 2024–May 2025, 1,506 services. Validation: July–November 2025, 1,177 services. Assessment: January–August 2026, 2,075 services. Property/package groups and mature outcome windows are separated. Calibration and threshold choices use validation only.

The source was already explored previously. This is a separate frozen historical comparison, not new independent prospective evidence. Age is a 1 km neighbourhood proxy, not actual building age. Frozen original sale links and retrospective geocodes/weather remain limitations.

## Results'''),nbformat.v4.new_code_cell('import pandas as pd\n'+f'display(pd.DataFrame({table!r}).round(3))'),nbformat.v4.new_markdown_cell('## Input coverage\nUnknown measurements stay missing; no age or rainfall values are invented.'),nbformat.v4.new_code_cell(f'display(pd.DataFrame({coverage!r}))'),nbformat.v4.new_markdown_cell('No replacement was automatically selected using these assessment scores. More historical comparison does not make these periods an untouched final test. Full protocols, artifact hashes, per-row predictions and uncertainty intervals remain beside the notebook. Notebook cells execute with the project harness; no native-kernel run.')]
    nb=nbformat.v4.new_notebook(cells=cells);execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Frozen_Age_Rain_Test.ipynb');export_html(nb,OUT/'Frozen_Age_Rain_Test.html')

if __name__=='__main__':main()
