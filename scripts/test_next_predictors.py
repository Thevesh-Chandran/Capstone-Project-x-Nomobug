"""Earlier-period paired feature tests; preserve all frozen and final-test artifacts."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import json,os
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import nbformat
from sklearn.neighbors import BallTree
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.research_callback_targets import calibration_split,digest
from scripts.build_supervisor_model_review import execute,export_html

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261017_next_predictor_test_v2'

def food_counts(frame,locations):
    eligible=frame[frame.location_uncertainty_radius_m.le(250)]
    addresses=sorted(set(eligible.address_hash)&set(locations.index))
    def fetch(address):
        pos=locations.loc[address];path=OUT/f'food_{address}_private.json'
        params={'bcircles':f'{pos.longitude},{pos.latitude},500','time':'2024-01-01,2025-01-01','filter':'(amenity=restaurant or amenity=cafe or amenity=fast_food or amenity=food_court) and type:node'}
        receipt={'parameters':params,'collected_utc':datetime.now(timezone.utc).isoformat()}
        try:
            with urlopen(Request('https://api.ohsome.org/v1/elements/count?'+urlencode(params),headers={'User-Agent':'Nomobug-capstone-research/1.0'}),timeout=30) as response:data=json.load(response)
            values={int(r['timestamp'][:4]):float(r['value']) for r in data['result']}
            assert set(values)=={2024,2025} and all(np.isfinite(v) and v>=0 for v in values.values())
            receipt.update(status='ok',response=data);path.write_text(json.dumps(receipt));return address,values
        except Exception as exc:
            receipt.update(status='failed',error_type=type(exc).__name__);path.write_text(json.dumps(receipt));return address,{}
    with ThreadPoolExecutor(max_workers=3) as pool:result=dict(pool.map(fetch,addresses))
    (OUT/'food_coverage.json').write_text(json.dumps({'eligible_unique_addresses':len(addresses),'successful_addresses':sum(bool(v) for v in result.values()),'precision_limit_m':250,'radius_m':500,'interpretation':'Approximate nearby mapped nodes; address uncertainty up to half the search radius. Not actual operating businesses.'},indent=2))
    return result

def historical_food():
    receipts=[];trees={}
    for year in [2024,2025]:
        path=OUT/f'public_food_nodes_{year}.json'
        params={'bboxes':'100.9,2.5,102.1,3.7','time':f'{year}-01-01','filter':'(amenity=restaurant or amenity=cafe or amenity=fast_food or amenity=food_court) and type:node','properties':'metadata'}
        receipt={'year':year,'endpoint':'https://api.ohsome.org/v1/elements/geometry','parameters':params,'collected_utc':datetime.now(timezone.utc).isoformat()}
        try:
            if not path.exists():
                with urlopen(Request(receipt['endpoint']+'?'+urlencode(params),headers={'User-Agent':'Nomobug-capstone-research/1.0'}),timeout=50) as response:data=json.load(response)
                assert data.get('type')=='FeatureCollection' and isinstance(data.get('features'),list)
                path.write_text(json.dumps(data))
            data=json.loads(path.read_text());points=[];seen=set()
            for item in data['features']:
                if item['geometry']['type']!='Point':continue
                ident=item.get('properties',{}).get('@osmId',item.get('id',str(item['geometry']['coordinates'])))
                if ident in seen:continue
                seen.add(ident);lon,lat=item['geometry']['coordinates'][:2];points.append([lat,lon])
            assert points
            trees[year]=BallTree(np.radians(points),metric='haversine')
            receipt.update(status='ok',nodes=len(points),sha256=digest(path))
        except Exception as exc:receipt.update(status='failed',error_type=type(exc).__name__)
        receipts.append(receipt);print('Historical food',year,receipt['status'],flush=True)
    (OUT/'food_source_receipts.json').write_text(json.dumps(receipts,indent=2))
    return trees

def previous_history(frame):
    """Only fully matured previous windows; these are windows, not unique claims."""
    result=pd.DataFrame(index=frame.index,columns=['same_pest_past_windows','same_pest_past_return_windows','same_pest_past_return_fraction'],dtype=float)
    for _,part in frame[frame.address_hash.notna()&frame.address_hash.ne('')].groupby(['address_hash','normalized_pest_category']):
        for idx,row in part.iterrows():
            prior=part[(part.outcome_end_date<row.anchor_date)&(part.anchor_date>=row.anchor_date-pd.Timedelta(days=180))]
            n=len(prior);k=int(prior[b.TARGET].sum())
            result.loc[idx]=[n,k,k/n if n else np.nan]
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    assert not (OUT/'protocol.json').exists(),'Preserve declared run'
    frozen=ROOT/'outputs/cp2-v2/prospective_callback_v2'
    hashes={p.name:digest(p) for p in frozen.iterdir() if p.is_file()}
    source=ROOT/'outputs/cp2-v2/source_refresh_20260927/refreshed/dataset_input.json'
    bundle=json.loads((frozen/'bundle.json').read_text());features=bundle['models']['challenger_all_history']['features']
    protocol={'declared_utc':datetime.now(timezone.utc).isoformat(),'code_sha256':digest(Path(__file__)),'source_sha256':digest(source),'frozen_hashes':hashes,'folds':b.DEVELOPMENT_FOLDS,'model':'et10_leaf5','decision':'Candidate only if AP increases and Brier decreases in all three paired development folds. No 2026 assessment or deployment.','food_scope':'January 1 historical mapped food nodes within 500m; uncertainty <=250m; approximate centroid counts, not exact proximity or operating-business census.','history_scope':'Exact normalized pest category and address; fully matured prior 30-day windows starting within 180 days; windows can share one return, not unique claim counts.','team_scope':'Exact date, summary and end-time source match; raw created/updated <=service end; continuity only when immediately preceding service team known.'}
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    f=c.prepare_input(b.load_dataset_input(source));f=f[f.anchor_date<pd.Timestamp('2026-01-01')].copy()
    f=f.join(previous_history(f))
    # Stable content identity join across snapshots, never raw row-number joins.
    archive=json.loads((ROOT/'outputs/cp2-v2/callback_evidence_reconciliation/source_private.json').read_text())['rows']['anchors']
    ar=pd.DataFrame(archive);ar.anchor_date=pd.to_datetime(ar.anchor_date)
    key=['sales_record_id','anchor_date','population']
    ar=ar[~ar.duplicated(key,keep=False)]
    raw=pd.read_csv(ROOT/'data/raw/calendar/nomobug_calendar_events_all_history.csv',keep_default_na=False)
    for name in ['start','end','created','updated']:raw[name+'_ts']=pd.to_datetime(raw[name],errors='coerce',utc=True)
    raw['local_date']=raw.start_ts.dt.tz_convert('Asia/Kuala_Lumpur').dt.tz_localize(None).dt.normalize()
    raw=raw[raw.created_ts.le(raw.updated_ts)&raw.updated_ts.le(raw.end_ts)&raw.end_ts.gt(raw.start_ts)&~raw.status.eq('cancelled')]
    raw=raw[~raw.duplicated(['summary','local_date','end_ts'],keep=False)]
    lookup={(r.summary,r.local_date,r.end_ts):r.calendar_name for r in raw.itertuples()}
    teams={}
    for row in ar.itertuples():
        end=pd.to_datetime(row.end_raw,errors='coerce',utc=True)
        teams[(row.sales_record_id,row.anchor_date,row.population)]=lookup.get((row.summary,row.anchor_date,end))
    f['research_team']=[teams.get(tuple(row)) for row in f[key].itertuples(index=False,name=None)]
    f['team_changed_from_previous']=np.nan
    for _,part in f.groupby('sales_record_id'):
        for idx,row in part.iterrows():
            prev=part[part.anchor_date<row.anchor_date].sort_values('anchor_date').tail(1)
            if len(prev) and pd.notna(row.research_team) and pd.notna(prev.iloc[0].research_team):f.loc[idx,'team_changed_from_previous']=float(row.research_team!=prev.iloc[0].research_team)
    locpath=ROOT/'outputs/model_validation/20261017_interservice_weather_v2/address_locations_private.json'
    loc=pd.read_json(locpath).drop_duplicates();counts=loc.groupby('address_hash').size()
    loc=loc[loc.address_hash.isin(counts[counts.eq(1)].index)].set_index('address_hash')
    food=food_counts(f,loc)
    f['historical_food_nodes_500m']=np.nan
    for idx,row in f.iterrows():
        if row.address_hash not in loc.index or pd.isna(row.location_uncertainty_radius_m) or row.location_uncertainty_radius_m>250:continue
        pos=loc.loc[row.address_hash];year=row.anchor_date.year
        if row.anchor_date<=pd.Timestamp(f'{year}-01-01'):continue
        f.loc[idx,'historical_food_nodes_500m']=food.get(row.address_hash,{}).get(year,np.nan)
    groups={'Pest-specific history':['same_pest_past_windows','same_pest_past_return_windows','same_pest_past_return_fraction'],'Team change':['team_changed_from_previous'],'Historical food places':['historical_food_nodes_500m']}
    coverage=[{'Input':name,'Known rows':int(f[col].notna().sum()),'Development rows':len(f)} for name,cols in groups.items() for col in cols]
    pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False)
    usable={name:cols for name,cols in groups.items() if any(f[col].nunique(dropna=True)>1 for col in cols)}
    variants={'Existing inputs':[]}|usable|{'All additions':sum(usable.values(),[])}
    rows=[]
    for fold,start,end in b.DEVELOPMENT_FOLDS:
        train,test,audit=b.purged_split(f,start,end);fit,cal,_=calibration_split(train)
        for variant,extra in variants.items():
            active=[x for x in extra if fit[x].nunique(dropna=True)>1]
            columns=features+active;numeric=[x for x in columns if x not in b.CATEGORICAL]
            pipe=c.make_pipeline('et10_leaf5',numeric)
            with threadpool_limits(limits=2):
                pipe.fit(fit[columns],fit[b.TARGET],classifier__sample_weight=c.training_weights(fit,'standard'))
                calibrator,_=b.fit_calibrator(cal[b.TARGET],pipe.predict_proba(cal[columns])[:,1])
                threshold=b.select_threshold(cal[b.TARGET],b.apply_calibrator(calibrator,pipe.predict_proba(cal[columns])[:,1]))
                metrics=b.score(test[b.TARGET],b.apply_calibrator(calibrator,pipe.predict_proba(test[columns])[:,1]),threshold)
            rows.append({'fold':fold,'variant':variant,'inputs':len(columns),'test_services':len(test),'test_returns':int(test[b.TARGET].sum()),**metrics})
            pd.DataFrame(rows).to_csv(OUT/'fold_metrics.csv',index=False);print(fold,variant,round(metrics['average_precision'],4),flush=True)
    results=pd.DataFrame(rows);base=results[results.variant.eq('Existing inputs')].set_index('fold');summary=[]
    for variant,part in results.groupby('variant',sort=False):
        part=part.set_index('fold');wins=((part.average_precision>base.average_precision)&(part.brier_score<base.brier_score)).sum()
        summary.append({'Inputs tested':variant,'Precision':part.precision.mean(),'Recall':part.recall.mean(),'F1':part.f1.mean(),'Average precision':part.average_precision.mean(),'Brier error':part.brier_score.mean(),'Periods improved on both':int(wins),'Decision':'Reference' if variant=='Existing inputs' else ('Promising candidate; confirmation needed' if wins==3 else 'No consistent improvement')})
    pd.DataFrame(summary).to_csv(OUT/'comparison.csv',index=False)
    assert hashes=={p.name:digest(p) for p in frozen.iterdir() if p.is_file()}
    acceptance={'frozen_unchanged':True,'fits':len(rows),'no_2026_test_used':True,'code_sha256':digest(Path(__file__)),'sources':{str(p.relative_to(ROOT)):digest(p) for p in [source,locpath,ROOT/'data/raw/calendar/nomobug_calendar_events_all_history.csv',ROOT/'outputs/cp2-v2/callback_evidence_reconciliation/source_private.json']},'limits':['Historical data previously explored; not an untouched final evaluation.','Calendar latest snapshot timing is conservative proxy, not full version history.','Team reflects assigned calendar, not individual technician or delivered treatment.','OSM nodes omit area-mapped businesses; zero means no mapped nodes, not no food establishments.','Annual map snapshot may be up to one year old. Geocodes reconstructed later; spatial context is exploratory.','Prior-window labels assumed available after full observation window; ingestion lag is not recoverable.']}
    (OUT/'acceptance.json').write_text(json.dumps(acceptance,indent=2))
    nb=nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell('# Do the new inputs help?\n\nSame model, same three 2025 validation periods. Thresholds and calibration use earlier data only. These are research comparisons, not new final accuracy.'),nbformat.v4.new_code_cell('import pandas as pd\nimport numpy as np\n'+f'display(pd.DataFrame({summary!r}).round(3))'),nbformat.v4.new_markdown_cell('## What the inputs mean\n\n**Pest-specific history:** previous completed service windows for the same pest and address, including how many had a return. This does not count unique warranty claims.\n\n**Team change:** whether the assigned calendar differs from the preceding paid service. Unknown matches stay missing.\n\n**Historical food places:** mapped restaurant/cafe/fast-food/food-court points within 500 metres, using January maps from before the service. Only uniquely mapped addresses with recorded uncertainty at most 250 metres (half the search radius) enter this feature. Missing stays unknown.'),nbformat.v4.new_code_cell(f'display(pd.DataFrame({coverage!r}))'),nbformat.v4.new_markdown_cell('## Limits\n\n'+'\n\n'.join(acceptance['limits'])+'\n\nNo live model was replaced. Notebook cells executed sequentially in Python; native Jupyter kernel not installed.\n\nSource: [ohsome extraction API](https://docs.ohsome.org/ohsome-api/development/endpoints.html). © OpenStreetMap contributors.')])
    execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'New_Inputs_Test.ipynb');export_html(nb,OUT/'New_Inputs_Test.html')
    print(pd.DataFrame(summary).to_string(index=False))

if __name__=='__main__':main()
