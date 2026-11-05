"""Exploratory, source-backed enquiry-to-recorded-sale test. Read-only warehouse.

The label is an exact contact match to a recorded sale, not verified conversion,
cash settlement or a lost-lead label. Outputs are private/aggregate only.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import hashlib, json, re
import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, precision_score, recall_score, f1_score, average_precision_score, roc_auc_score, brier_score_loss
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261021_enquiry_conversion'
PROJECT='profound-keel-500007-s4'
MAX_BYTES=100*1024*1024
SEED=20261021
CAT=['channel','premise','pest']
NUM=['month_sin','month_cos','weekday_sin','weekday_cos']
FEATURES=CAT+NUM
FAMILIES=['plain_logistic','balanced_logistic','random_forest','extra_trees','boosting']
THRESHOLDS=[.005,.01,.02,.03,.05,.075,.1,.15,.2,.3,.4,.5,.6,.7,.8,.9]

def save(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,default=str,allow_nan=False),encoding='utf-8')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def protocol():
    OUT.mkdir(parents=True,exist_ok=True)
    p=OUT/'protocol.json'
    if p.exists():return
    save(p,{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':digest(__file__),
      'question':'After a first recorded staff reply, will the same reviewed contact have a matching recorded included sale in days1–30?',
      'decision':'Research channel-level acquisition/followup planning; no automatic customer actions.',
      'scope':'2026 prospect tab; first parseable dated reply per unambiguous Malaysian mobile contact; contacts disjoint across partitions.',
      'partitions':{'train':['2026-01-01','2026-03-31'],'validation':['2026-05-01','2026-06-30'],'assessment':['2026-08-01','2026-09-16']},
      'outcome_horizon_days':30,'label':'Matching included SALES row with strict later local closed date1–30days; no match means no matching recorded sale, not lost or known no purchase.',
      'exclude':'Ambiguous/multiple phone, shared sale contact across differently recorded names, past buyer before first reply, same-day sale, missing/inferred sale close year, missing first reply; outcome horizon must mature before common extraction local date.',
      'features':FEATURES,'blocked_features':['Names/phones/IDs','booking','conversation status','WON remark','objection category','payment status','future followups','closing dates','sales amount'],
      'families':FAMILIES,'thresholds':THRESHOLDS,
      'selection':'Two declared policies: highest validation F1; highest precision subject to recall>=0.30 and >=20 validation alerts. Same train/validation partitions. Select before assessment; no assessment tuning.',
      'research_gate':'Assessment >=20positives; precision>=0.50; recall>=0.30; balanced accuracy>0.5; improvement over constant/always-no/always-yes baselines; source/label review still needed.',
      'limitations':['Retrospective initial recorded fields lack per-field time history','Exact contact sale linkage is a proxy, not verified causal enquiry attribution','2026 source firstreply date has no time of day','Raw staff/customer type/pest/channel can have later edits','Historical periods already inspected in other research','No model promotion or frozen prospective changes'],
      'protected':{str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json',ROOT/'config/cp2_model_current.json']}})

def extract():
    target=OUT/'common_source_private.json'
    if target.exists():return json.loads(target.read_text())
    client=bigquery.Client(project=PROJECT,location='asia-southeast1');receipts=[]
    def q(sql):
        dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False))
        if (dry.total_bytes_processed or 0)>MAX_BYTES:raise ValueError('100MiB dry-run limit')
        job=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES))
        rows=[dict(r.items()) for r in job.result(timeout=120)]
        receipts.append({'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,'dry_run_bytes':dry.total_bytes_processed,'row_count':len(rows),'sql':sql})
        return rows
    try:
        head=q(f"SELECT manifest_json FROM `{PROJECT}.audit.release_runs` WHERE status='PUBLISHED' ORDER BY event_at DESC LIMIT 1")
        manifest=head[0]['manifest_json']
        if isinstance(manifest,str):manifest=json.loads(manifest)
        prefix='cp2r_'+manifest['run_id']
        if not re.fullmatch(r'cp2r_[a-zA-Z0-9_]+',prefix):raise ValueError('Invalid prefix')
        # Same published release for prospects, SALES and dated included sale facts.
        prospects=q(f'''SELECT source_sheet_row,phone_raw_trimmed,first_reply_date,acquisition_group,
          campaign_code,customer_type,pest_category,first_reply_needs_review
          FROM `{PROJECT}.{prefix}_silver.prospects_2026` WHERE row_class='prospect_candidate' ''')
        sales=q(f'''SELECT s.sales_record_id,s.phone_raw,s.customer_name_raw,f.closed_date,
          f.closed_date_year_source,f.include_in_sale_count
          FROM `{PROJECT}.{prefix}_silver.sales` s
          JOIN `{PROJECT}.{prefix}_gold.sales_package_facts` f USING(sales_row_id)''')
        data={'manifest':manifest,'prospects':prospects,'sales':sales}
        save(target,data);save(OUT/'source_receipt.json',{'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'release':prefix,'manifest':manifest,'queries':receipts,'private_export_sha256':digest(target)})
        return json.loads(target.read_text())
    except Exception as exc:
        save(OUT/'source_failure.json',{'type':type(exc).__name__,'message':str(exc)[:1200],'completed_queries':receipts})
        raise
    finally:client.close()

def phone(raw):
    raw=str(raw or '').strip()
    if re.search(r'[/,;]|[A-Za-z]',raw):return None
    value=re.sub(r'\D','',raw)
    if value.startswith('0060'):value=value[2:]
    if value.startswith('0'):value='60'+value[1:]
    return value if re.fullmatch(r'601\d{8,9}',value) else None

def dataset(raw):
    end=min(pd.Timestamp(raw['manifest']['extracted_at'][k]).tz_convert('Asia/Kuala_Lumpur').date() for k in ['2026','SALES'])
    sale_contacts=defaultdict(list);all_sale_contacts=defaultdict(list);sale_audit=Counter()
    for s in raw['sales']:
        if not s['include_in_sale_count']:continue
        p=phone(s.get('phone_raw'))
        if not p:sale_audit['no_single_mobile_phone']+=1;continue
        name=re.sub(r'\W','',str(s.get('customer_name_raw') or '').casefold())
        all_sale_contacts[p].append(s)
        if not s.get('closed_date') or s.get('closed_date_year_source')!='entry_timestamp':sale_audit['unresolved_or_inferred_sale_year']+=1;continue
        sale_contacts[p].append((name,pd.Timestamp(s['closed_date']).date()))
    ambiguous={p for p,vals in all_sale_contacts.items() if len({re.sub(r'\W','',str(s.get('customer_name_raw') or '').casefold()) for s in vals})!=1}
    uncertain={p for p,v in all_sale_contacts.items() if any(not s.get('closed_date') or s.get('closed_date_year_source')!='entry_timestamp' for s in v)}
    first=defaultdict(list);exclusions=Counter()
    for p in raw['prospects']:
        key=phone(p.get('phone_raw_trimmed'))
        if not key:exclusions['no_single_valid_mobile']+=1;continue
        if not p.get('first_reply_date'):exclusions['no_first_reply_date']+=1;continue
        first[key].append(p)
    rows=[]
    for key,vals in first.items():
        vals=sorted(vals,key=lambda r:(r['first_reply_date'],r['source_sheet_row']))
        p=vals[0];date=pd.Timestamp(p['first_reply_date']).date()
        # Different initial features for the exact same day are ambiguous; do not choose later facts.
        initial=[a for a in vals if a['first_reply_date']==p['first_reply_date']]
        if len({(a['acquisition_group'],a['customer_type'],a['pest_category']) for a in initial})!=1:exclusions['same_day_initial_feature_conflict']+=1;continue
        if key in ambiguous:exclusions['shared_sale_phone_different_names']+=1;continue
        if key in uncertain:exclusions['sale_date_uncertainty']+=1;continue
        dates=[d for name,d in sale_contacts.get(key,[])]
        if any(d<date for d in dates):exclusions['existing_recorded_customer']+=1;continue
        if any(d==date for d in dates):exclusions['same_day_sale_time_unknown']+=1;continue
        enddate=date+pd.Timedelta(days=30)
        if enddate>end:exclusions['immature_outcome']+=1;continue
        rows.append({'contact_hash':hashlib.sha256(key.encode()).hexdigest(),'date':str(date),'outcome_end':str(enddate),
          'label':int(any(date<d<=enddate for d in dates)),
          'channel':p['acquisition_group'] or 'Unknown','premise':p['customer_type'] or 'Unknown','pest':p['pest_category'] or 'Unknown',
          'month_sin':float(np.sin(date.month*2*np.pi/12)),'month_cos':float(np.cos(date.month*2*np.pi/12)),
          'weekday_sin':float(np.sin(date.weekday()*2*np.pi/7)),'weekday_cos':float(np.cos(date.weekday()*2*np.pi/7))})
    d=pd.DataFrame(rows);d['date']=pd.to_datetime(d.date);d['outcome_end']=pd.to_datetime(d.outcome_end)
    assert not d.contact_hash.duplicated().any()
    audit={'observed_through_local':str(end),'raw_enquiry_candidates':len(raw['prospects']),'raw_included_sales':sum(bool(s['include_in_sale_count']) for s in raw['sales']),
      'unique_valid_mobile_with_reply':len(first),'excluded_contacts':dict(exclusions),'sale_rows_excluded':dict(sale_audit),
      'eligible':len(d),'positives':int(d.label.sum()),'by_month':d.assign(month=d.date.dt.strftime('%Y-%m')).groupby('month').label.agg(['size','sum']).reset_index().to_dict('records')}
    save(OUT/'dataset_audit.json',audit);d.to_csv(OUT/'dataset_private.csv',index=False)
    return d

def estimator(name):
    preprocessing=ColumnTransformer([('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),CAT),('num',make_pipeline(SimpleImputer(strategy='median'),StandardScaler()),NUM)])
    if name in ['plain_logistic','balanced_logistic']:m=LogisticRegression(C=1,class_weight='balanced' if name.startswith('balanced') else None,max_iter=1000,random_state=SEED)
    elif name=='random_forest':m=RandomForestClassifier(n_estimators=150,max_depth=5,min_samples_leaf=20,class_weight='balanced',n_jobs=2,random_state=SEED)
    elif name=='extra_trees':m=ExtraTreesClassifier(n_estimators=150,max_depth=5,min_samples_leaf=20,class_weight='balanced',n_jobs=2,random_state=SEED)
    else:m=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=7,min_samples_leaf=30,l2_regularization=10,early_stopping=False,random_state=SEED)
    return make_pipeline(preprocessing,m)

def metrics(y,p,t):
    y=np.asarray(y,dtype=int);z=np.asarray(p)>=t
    return {'n':len(y),'positives':int(y.sum()),'alerts':int(z.sum()),'tp':int(np.sum(z&(y==1))),'fp':int(np.sum(z&(y==0))),'fn':int(np.sum(~z&(y==1))),'tn':int(np.sum(~z&(y==0))),
      'accuracy':float(accuracy_score(y,z)),'balanced_accuracy':float(balanced_accuracy_score(y,z)),
      'precision':float(precision_score(y,z,zero_division=0)),'recall':float(recall_score(y,z,zero_division=0)),'f1':float(f1_score(y,z,zero_division=0)),
      'average_precision':float(average_precision_score(y,p)),'roc_auc':float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None,'brier':float(brier_score_loss(y,p)),
      'prevalence':float(y.mean())}

def run():
    protocol()
    if (OUT/'results.json').exists():raise RuntimeError('Assessment already completed; do not overwrite')
    raw=extract();d=dataset(raw);pr=json.loads((OUT/'protocol.json').read_text())
    parts={k:d[d.date.between(*v)].copy() for k,v in pr['partitions'].items()}
    train,val,test=[parts[k] for k in ['train','validation','assessment']]
    assert train.outcome_end.max()<val.date.min() and val.outcome_end.max()<test.date.min()
    assert all(not set(parts[a].contact_hash)&set(parts[b].contact_hash) for a,b in [('train','validation'),('validation','assessment'),('train','assessment')])
    save(OUT/'partition_audit.json',{k:{'n':len(v),'positives':int(v.label.sum()),'min_date':v.date.min(),'max_date':v.date.max(),'max_outcome':v.outcome_end.max()} for k,v in parts.items()})
    if any(len(v)<100 or v.label.sum()<10 for v in parts.values()):
        save(OUT/'not_trained.json',{'reason':'Insufficient partition population or positive labels; no fabricated/resplit test'});return
    fitted={};search=[]
    with threadpool_limits(limits=2):
      for name in FAMILIES:
        m=estimator(name);m.fit(train[FEATURES],train.label);p=m.predict_proba(val[FEATURES])[:,1];fitted[name]=m
        for t in THRESHOLDS:search.append({'model':name,'threshold':t,**metrics(val.label,p,t)})
    pd.DataFrame(search).to_csv(OUT/'validation_search.csv',index=False)
    eligible=[r for r in search if r['recall']>=.30 and r['alerts']>=20]
    policies={'f1':max(search,key=lambda r:(r['f1'],r['precision'])),'precision':max(eligible or search,key=lambda r:(r['precision'],r['f1']))}
    save(OUT/'selection_before_assessment.json',{'selected_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':digest(OUT/'protocol.json'),'policies':policies})
    results=[]
    for name,c in policies.items():
        p=fitted[c['model']].predict_proba(test[FEATURES])[:,1];met=metrics(test.label,p,c['threshold'])
        rng=np.random.default_rng(SEED);samples=[]
        for _ in range(1000):
            idx=rng.integers(0,len(test),len(test));y=test.label.to_numpy()[idx];z=p[idx]>=c['threshold']
            tp=int(np.sum(z&(y==1)));fp=int(np.sum(z&(y==0)));fn=int(np.sum(~z&(y==1)))
            samples.append([tp/max(1,tp+fp),tp/max(1,tp+fn)])
        ci=np.quantile(samples,[.025,.975],axis=0).T.tolist()
        pd.DataFrame({'contact_hash':test.contact_hash,'date':test.date,'actual':test.label,'probability':p,'alert':p>=c['threshold']}).to_csv(OUT/f'{name}_assessment_private.csv',index=False)
        results.append({'policy':name,'selected':c,'assessment':met,'precision_ci95':ci[0],'recall_ci95':ci[1],
          'research_gate_passed':bool(met['positives']>=20 and met['precision']>=.5 and met['recall']>=.3 and met['balanced_accuracy']>.5),
          'operationally_validated':False})
    base=float(train.label.mean())
    save(OUT/'results.json',{'question':pr['question'],'inputs':FEATURES,'models_tested':len(FAMILIES),'model_threshold_combinations':len(search),
      'results':results,'baselines':{'always_no':metrics(test.label,np.full(len(test),base),1.01),'always_yes':metrics(test.label,np.full(len(test),base),0),'constant_probability':base},
      'protected_unchanged':all(digest(ROOT/path)==h for path,h in pr['protected'].items()),
      'limitations':pr['limitations'],'completed_at_utc':datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'selected':policies,'assessment':results,'always_no_accuracy':1-float(test.label.mean())},indent=2))

if __name__=='__main__':run()
