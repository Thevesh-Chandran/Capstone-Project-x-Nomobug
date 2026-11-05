"""Bounded paired test of official DOSM district context and lagged national CPI.

Exploratory retrospective comparison; no cloud writes/model promotion.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib, json, re
import numpy as np
import pandas as pd
import joblib
from sklearn.base import clone
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.evaluate_larger_frozen_model import make_partitions,bootstrap_intervals
from webapp.geography import contains,edge_distance_km

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'outputs/model_validation/20261021_dosm_inputs'
OUT=SOURCES/'trusted_geography_v2'
HIES=['district2022_median_income_rm','district2022_mean_expenditure_rm','district2022_poverty_pct','district2022_context_unknown']
CPI=['lag2_headline_cpi_index','lag2_headline_cpi_yoy_pct']
DATE=['months_since_jan2024']
VARIANTS={'baseline':[],'plus_hies2022':HIES,'plus_lag2_cpi':CPI,'plus_both':HIES+CPI,'date_proxy_control':DATE}

def save(path,obj):Path(path).write_text(json.dumps(obj,indent=2,default=str,allow_nan=False),encoding='utf-8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def declare():
    OUT.mkdir(exist_ok=True)
    if (OUT/'protocol.json').exists():return
    protected=[ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json',ROOT/'outputs/cp2-v2/prospective_callback_v2/challenger_all_history.joblib',ROOT/'config/cp2_model_current.json']
    save(OUT/'protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),
      'target':'Recorded corrective Calendar return within30days after paid service; not adjudicated claims/biological recurrence.',
      'source':'Same protected Sept27modeldataset and original93-input pipeline settings as separate2075-service historical comparison.',
      'partitions':'Original fixed1506training/1177validation/2075assessment; disjoint property/package groups; training outcomes complete beforeJuly2025, validation outcomes complete beforeJan2026.',
      'variants':VARIANTS,'fit_budget':5,'calibration':'Platt calibration and maximum-F1 threshold on unchanged2025validation only. No classifier refit on calibration/assessment.',
      'selection':'ValidationF1 first, thenAP; compare every predeclared variant on assessment without selecting a new winner from test.',
      'hies_time':'Use only2022reference rows. OriginalHIES2022release28Jul2023; officialdistrictcatalogue initialpublication6Oct2023; conservative context availability27Nov2023 MyLocalStats2022districtrelease. Currentdownloadvintage maycontain laterrevisions; no original2023fileversion recovered. Never use2024reference rows.',
      'cpi_time':'Reference month exactly two calendar months before anchor. ActualDOSMrelease date for that reference month must precede anchor. Latestdownloadvintage maycontain revisions; not a true original as-issued archive.',
      'geography':'Exactsourceaddresshash tounique savedcoordinate, checked againstmatchingcoordinate in savedgeoapify_pilot_v17 trustedtiers. Originalmodelsource hasuncertaintybutnotier. Spatialdistrict contains coordinate and isfartherthanuncertainty+100m fromboundary. Nofuzzyname/address joins. Districtcontextisnotindividualincome.',
      'controls':'Compare an ordinalmonth date-proxy control because CPItrend mayonly encode time; no assessmenttuning.',
      'limitations':['Historical assessment previouslyexamined','Current-vintage externaldata cannotproveoriginalas-issuedvalues','Retrospective geocoding with uncertain/missingdistricts','Onlyfew distinctdistrictcontextvalues','No causal or customer-income conclusion','No automaticproductionpromotion'],
      'protected':{str(p.relative_to(ROOT)):sha(p) for p in protected},
      'external_files':{p.name:sha(p) for p in [SOURCES/'hies_district.csv',SOURCES/'cpi_2d.csv',SOURCES/'cpi_release_archive.html']},
      'implementation_amendment':'Original5fitrun incorrectlyreliedonuncertaintywithoutmetadata-tiergate. ItsHIEScomparisonsinvalidandpreservedinparentfolder. V2strictlychecksmetadataandcoordinatesbefore5repeatfits. Total10classifierfits; noassessment-basedfeature/settingsselection. Previouslyseenperiodremainsadaptivehistoricalresearch.'})

def geographic_context(frame):
    path=ROOT/'outputs/model_validation/20261017_interservice_weather_v2/address_locations_private.json'
    loc=pd.read_json(path).drop_duplicates();count=loc.groupby('address_hash').size();loc=loc[loc.address_hash.isin(count[count.eq(1)].index)].set_index('address_hash')
    boundary_path=ROOT/'data/processed/boundaries/dosm_districts.geojson'
    boundaries=json.loads(boundary_path.read_text())['features'];boxes=[]
    for f in boundaries:
        polys=f['geometry']['coordinates'] if f['geometry']['type']=='MultiPolygon' else [f['geometry']['coordinates']]
        pts=[point for poly in polys for ring in poly for point in ring]
        xs=[p[0] for p in pts];ys=[p[1] for p in pts]
        boxes.append((min(xs),min(ys),max(xs),max(ys),f))
    trusted={'precise_candidate','street_candidate','manual_verified','area_reference_verified','postcode_area_candidate'}
    metadata_path=ROOT/'data/processed/geocoding/geoapify_pilot_v17.jsonl'
    metadata=[json.loads(line) for line in metadata_path.read_text().splitlines() if line.strip()]
    if len({r['address_hash'] for r in metadata})!=len(metadata):raise ValueError('Duplicate geocode metadata hash')
    metadata={r['address_hash']:r for r in metadata}
    cache={};values=[];reasons=Counter()
    for row in frame.itertuples():
        key=row.address_hash;u=row.location_uncertainty_radius_m
        if key not in loc.index or not np.isfinite(u) or u<0:
            values.append(None);reasons['no_unique_coordinate_or_uncertainty']+=1;continue
        meta=metadata.get(key,{})
        if meta.get('precision_tier') not in trusted:
            values.append(None);reasons['untrusted_precision_tier']+=1;continue
        a=loc.loc[key];lat=float(a.latitude);lon=float(a.longitude);ck=(key,float(u))
        if not all(isinstance(meta.get(x),(int,float)) for x in ['latitude','longitude']) or not np.allclose([lat,lon],[meta['latitude'],meta['longitude']],atol=1e-7,rtol=0):
            values.append(None);reasons['metadata_coordinate_mismatch']+=1;continue
        if ck not in cache:
            candidates=[f for x0,y0,x1,y1,f in boxes if x0<=lon<=x1 and y0<=lat<=y1 and contains(f['geometry'],lon,lat)]
            f=candidates[0] if len(candidates)==1 else None
            cache[ck]=(f['properties']['state']+' / '+f['properties']['district']) if f and edge_distance_km(f['geometry'],lon,lat)>u/1000+.1 else None
        values.append(cache[ck]);reasons['assigned' if cache[ck] else 'boundary_uncertainty_or_outside']+=1
    frame['dosm_district_context']=values
    h=pd.read_csv(SOURCES/'hies_district.csv');h=h[h.date.eq('2022-01-01')].copy()
    h['district_key']=h.state+' / '+h.district
    assert h.district_key.is_unique
    h=h.set_index('district_key')
    for new,old in zip(HIES[:3],['income_median','expenditure_mean','poverty']):frame[new]=frame.dosm_district_context.map(h[old])
    frame[HIES[3]]=frame[HIES[0]].isna().astype(int)
    unjoined=sorted(set(frame.dosm_district_context.dropna())-set(h.index))
    if frame[HIES[0]].notna().sum()<100:raise ValueError('Insufficient HIES district join coverage')
    return {'location_source_sha256':sha(path),'trusted_tier_metadata_sha256':sha(metadata_path),'boundaries_sha256':sha(boundary_path),'district2022_rows':len(h),'reference_years_in_download':sorted(pd.read_csv(SOURCES/'hies_district.csv').date.unique()),'used_year':2022,'assignment_reasons':dict(reasons),'unmatched_public_district_labels':unjoined,'districts_matched':int(frame.loc[frame[HIES[0]].notna(),'dosm_district_context'].nunique())}

def cpi_context(frame):
    data=pd.read_csv(SOURCES/'cpi_2d.csv');data=data[data.division.eq('overall')].set_index('date')['index'];assert data.index.is_unique
    archive=json.loads((SOURCES/'cpi_release_dates_parsed.json').read_text());release={}
    for d,month,y in archive['matches']:
        reference=pd.to_datetime(f'1 {month} {y}',format='%d %B %Y').strftime('%Y-%m-01')
        date=pd.to_datetime(d,format='%d.%m.%Y')
        if reference in release and release[reference]!=date:raise ValueError('Conflicting CPIrelease dates')
        release[reference]=date
    records=[];lag_index=[];yoy=[]
    for anchor in frame.anchor_date:
        ref=anchor.to_period('M').to_timestamp()-pd.DateOffset(months=2);key=ref.strftime('%Y-%m-%d');prior=(ref-pd.DateOffset(years=1)).strftime('%Y-%m-%d')
        if key not in release or release[key]>=anchor or key not in data or prior not in data:raise ValueError('CPIasofcoverage failure '+key)
        lag_index.append(float(data[key]));yoy.append(float(100*(data[key]/data[prior]-1)));records.append((key,str(release[key].date())))
    frame[CPI[0]]=lag_index;frame[CPI[1]]=yoy;frame[DATE[0]]=(frame.anchor_date.dt.year-2024)*12+frame.anchor_date.dt.month-1
    return {'monthly_references':sorted(set(records)),'coverage':len(frame),'minimum_lag_months':2,'release_before_every_anchor':True,'latest_raw_reference':max(data.index),'latest_used_reference':max(r[0] for r in records),'current_vintage_revision_risk':True}

def pipeline_copy(template,new):
    m=clone(template);m.named_steps['classifier'].set_params(n_jobs=2)
    pre=m.steps[0][1];pre.set_params(transformers=[(name,tr,list(cols)+new if name=='numeric' else list(cols)) for name,tr,cols in pre.transformers])
    return m

def run():
    declare()
    if (OUT/'results.json').exists():raise ValueError('Completed assessment must not be overwritten')
    original=ROOT/'outputs/cp2-v2/prospective_callback_v2';bundle=json.loads((original/'bundle.json').read_text());source=ROOT/bundle['training_input_relative_path']
    assert sha(source)==bundle['input_file_sha256']
    frame=c.prepare_input(b.load_dataset_input(source));geo=geographic_context(frame);cpi=cpi_context(frame)
    train,val,test=make_partitions(frame);assert (len(train),len(val),len(test))==(1506,1177,2075)
    save(OUT/'coverage.json',{'geography':geo,'cpi':cpi,'partitions':{name:{'n':len(part),'returns':int(part[b.TARGET].sum()),'hies_known':int(part[HIES[0]].notna().sum()),'cpi_known':int(part[CPI].notna().all(axis=1).sum())} for name,part in [('train',train),('validation',val),('assessment',test)]}})
    frame[c.KEYS+['dosm_district_context']+HIES+CPI+DATE].to_pickle(OUT/'new_inputs_private.pkl')
    old=joblib.load(original/'challenger_all_history.joblib');base=list(old['members'][0]['features']);template=old['members'][0]['pipeline'];assert len(base)==93
    fits=[]
    for name,new in VARIANTS.items():
        cols=base+new;m=pipeline_copy(template,new)
        with threadpool_limits(limits=2):
            m.fit(train[cols],train[b.TARGET],classifier__sample_weight=np.ones(len(train)))
            raw=m.predict_proba(val[cols])[:,1];cal,_=b.fit_calibrator(val[b.TARGET],raw);prob=b.apply_calibrator(cal,raw);threshold=b.select_threshold(val[b.TARGET],prob)
        artifact={'pipeline':m,'features':cols,'calibrator':cal,'threshold':threshold,'validation_metrics':b.score(val[b.TARGET],prob,threshold),'frozen_at_utc':datetime.now(timezone.utc).isoformat()}
        joblib.dump(artifact,OUT/(name+'.joblib'));fits.append({'variant':name,'model_sha256':sha(OUT/(name+'.joblib')),'input_count':len(cols),'validation':artifact['validation_metrics'],'threshold':threshold,'frozen_at_utc':artifact['frozen_at_utc']})
        print('Frozen',name,flush=True)
    selected=max(fits,key=lambda r:(r['validation']['f1'],r['validation']['average_precision']))['variant']
    save(OUT/'frozen_manifest.json',{'all_frozen_before_assessment':True,'models':fits,'validation_choice':selected})
    results=[];pred={}
    for one in fits:
        name=one['variant'];assert sha(OUT/(name+'.joblib'))==one['model_sha256'];a=joblib.load(OUT/(name+'.joblib'))
        with threadpool_limits(limits=2):p=b.apply_calibrator(a['calibrator'],a['pipeline'].predict_proba(test[a['features']])[:,1])
        tn,fp,fn,tp=confusion_matrix(test[b.TARGET],p>=a['threshold'],labels=[False,True]).ravel()
        met=b.score(test[b.TARGET],p,a['threshold']);pred[name]=p
        if name=='baseline':
            known=pd.read_csv(ROOT/'outputs/model_validation/20261017_larger_frozen_test/test_predictions_private.csv')
            assert np.allclose(p,known.probability,rtol=0,atol=1e-12),'Baseline failed identical-record reproduction'
        results.append({'variant':name,'inputs':len(a['features']),'threshold':a['threshold'],'assessment':met,'tp':int(tp),'fp':int(fp),'fn':int(fn),'tn':int(tn),'ci95':bootstrap_intervals(test,p,a['threshold'],repeats=1000)})
        test[c.KEYS+['validation_group',b.TARGET]].assign(probability=p).to_csv(OUT/(name+'_assessment_private.csv'),index=False)
    protected=json.loads((OUT/'protocol.json').read_text())['protected'];assert all(sha(ROOT/p)==h for p,h in protected.items())
    baseline_trainmean=float(train[b.TARGET].mean());y=test[b.TARGET].to_numpy(dtype=float)
    save(OUT/'results.json',{'validation_choice':selected,'results':results,'baseline_train_prevalence':baseline_trainmean,'assessment_prevalence':float(y.mean()),'constant_training_prevalence_brier':float(np.mean((y-baseline_trainmean)**2)),'always_no':b.score(y,np.zeros(len(y)),.5),'protected_unchanged':True,'source_sha256':sha(source),'actual_classifier_fits':len(fits),'exploratory_not_original_vintage_backtest':True,'completed_at_utc':datetime.now(timezone.utc).isoformat()})
    print(json.dumps([{'variant':r['variant'],**r['assessment']} for r in results],indent=2))

if __name__=='__main__':run()
