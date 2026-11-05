"""Bounded useful return-target search; validation-led precision/recall policies."""
from pathlib import Path
from datetime import datetime,timezone
import itertools,json
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier,HistGradientBoostingClassifier
from sklearn.metrics import precision_recall_curve,confusion_matrix
from threadpoolctl import threadpool_limits
import joblib
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.research_callback_targets import labels,calibration_split
from scripts.test_calendar_note_predictors import PATTERNS,extract
from scripts.reconcile_callback_evidence import snapshot_known_by_service_end
from scripts.test_compact_notes_rain import make_model
from scripts.research_expanded_targets import ROOT,save,sha

OUT=ROOT/'outputs/model_validation/20261021_precision_targets'
SEED=20261021
MODELS=['logistic','random_forest','extra_trees','boosting','catboost']
THRESHOLDS=[.01,.025,.05,.075,.1,.125,.15,.175,.2,.25,.3,.4,.5,.6,.7,.8,.9]
START=pd.Timestamp('2026-04-01');END=pd.Timestamp('2026-07-15');COMPLETE=pd.Timestamp('2026-09-13')
TARGETS={'each_service_30':(30,'all'),'residential_3x_final_30':(30,'three'),'residential_final_60':(60,'final')}

def score(y,p,t):return b.score(np.asarray(y,dtype=bool),np.asarray(p),t)

def decision(rows,policy):
    useful=[r for r in rows if r['recall']>=.2 and r['alert_rows']>=10]
    if not useful:return None
    if policy=='precision':return max(useful,key=lambda r:(r['precision'],r['f1'],r['threshold']))
    if policy=='balanced':return max(useful,key=lambda r:(r['balanced_accuracy'],r['precision'],r['threshold']))
    return max(useful,key=lambda r:(r['f1'],r['precision'],r['threshold']))

def classifier(name,cols):
    pipe=make_model('Extra Trees',cols)
    if name=='logistic':est=LogisticRegression(C=.3,max_iter=600,random_state=SEED)
    elif name=='random_forest':est=RandomForestClassifier(n_estimators=150,max_depth=6,min_samples_leaf=8,class_weight='balanced',random_state=SEED,n_jobs=2)
    elif name=='extra_trees':est=ExtraTreesClassifier(n_estimators=150,max_depth=10,min_samples_leaf=5,class_weight='balanced',random_state=SEED,n_jobs=2)
    elif name=='boosting':est=HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=7,min_samples_leaf=20,l2_regularization=10,early_stopping=False,random_state=SEED)
    else:
        from catboost import CatBoostClassifier
        est=CatBoostClassifier(iterations=150,depth=4,learning_rate=.04,l2_leaf_reg=12,verbose=False,thread_count=2,allow_writing_files=False,random_seed=SEED)
    pipe.set_params(classifier=est);return pipe

def datasets():
    cfg=json.loads((ROOT/'config/cp2_target_research_20261016.json').read_text())
    source=ROOT/cfg['inputs']['features']['path'];f=c.prepare_input(b.load_dataset_input(source))
    facts=pd.DataFrame(json.loads((ROOT/cfg['inputs']['facts']['path']).read_text()));facts.event_date_local=pd.to_datetime(facts.event_date_local)
    assert len(f)==5598
    replay=labels(f,facts,30,COMPLETE);assert replay[b.TARGET].astype(bool).tolist()==f[b.TARGET].astype(bool).tolist()
    evidence=ROOT/'outputs/cp2-v2/callback_evidence_reconciliation/source_private.json';raw=json.loads(evidence.read_text());a=pd.DataFrame(raw['rows']['anchors']);a.anchor_date=pd.to_datetime(a.anchor_date)
    assert not a.duplicated(c.KEYS).any();known=[snapshot_known_by_service_end(r) for r in raw['rows']['anchors']]
    notes=pd.DataFrame([extract(t) if k else {x:np.nan for x in PATTERNS} for t,k in zip(a.description,known)])
    a=pd.concat([a,notes],axis=1);a['notes_unknown']=1-np.array(known,dtype=int)
    f=f.merge(a[c.KEYS+list(PATTERNS)+['notes_unknown']],on=c.KEYS,how='left',validate='one_to_one');f.notes_unknown=f.notes_unknown.fillna(1)
    # Final-stage eligibility uses only paid stages dated no later than the anchor.
    paid=facts[facts.event_category.eq('service')&~facts.warranty_claim_candidate.eq(True)]
    groups={str(s):g for s,g in paid.groupby('sales_record_id')};complete=[]
    for r in f.itertuples():
        n=r.package_sessions_recorded;g=groups.get(str(r.sales_record_id));ok=False
        if g is not None and pd.notna(n) and int(n)==n and n>=1 and r.service_number==n:
            p=g[g.event_date_local.le(r.anchor_date)&g.session_total.eq(n)&g.session_current.between(1,n)]
            ok=len(p)==int(n) and set(p.session_current)==set(range(1,int(n)+1))
        complete.append(ok)
    f['complete_final']=complete
    compact=json.loads((ROOT/'outputs/model_validation/20261018_compact_notes_rain/protocol.json').read_text())['candidates']['Service + pest + history']
    extra_path=ROOT/'outputs/model_validation/20261018_frozen_age_rain/new_inputs_private.pkl';extra=pd.read_pickle(extra_path)
    raincols=[x for x in extra if x not in c.KEYS and not x.startswith('settlement_')]
    f=f.merge(extra[c.KEYS+raincols],on=c.KEYS,how='left',validate='one_to_one');f.interval_rain_unknown=f.interval_rain_unknown.fillna(1)
    full=json.loads((ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json').read_text())['models']['challenger_all_history']['features']
    feature_sets={'compact':compact,'compact_notes':compact+list(PATTERNS)+['notes_unknown'],
        'full_notes_rain':full+list(PATTERNS)+['notes_unknown']+raincols}
    result={}
    for name,(days,pop) in TARGETS.items():
        d=labels(f,facts,days,COMPLETE)
        if pop=='three':d=d[d.premise_type.eq('RESIDENTIAL')&d.package_sessions_recorded.eq(3)&d.complete_final]
        if pop=='final':d=d[d.premise_type.eq('RESIDENTIAL')&d.complete_final]
        result[name]=d
    return result,feature_sets,{str(p.relative_to(ROOT)):sha(p) for p in [source,ROOT/cfg['inputs']['facts']['path'],evidence,extra_path]}

def main():
    OUT.mkdir(parents=True,exist_ok=True);assert not (OUT/'protocol.json').exists()
    protected={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'outputs/cp2-v2/prospective_callback_v2').iterdir() if p.is_file()}
    save(OUT/'protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),'protected':protected,
        'targets':TARGETS,'models':MODELS,'feature_sets':['compact','compact_notes','full_notes_rain'],'histories':['all','365days'],
        'development':['2025Q3','2025Q4','2026Q1 mature before April1'],'assessment':['2026-04-01','2026-07-15'],
        'method':'Label maturity embargo and property/package purge. Fit/calibration separated chronologically within each development fold. Select candidates and thresholds using pooled development predictions; validation labels must mature before April1. Final classifier/calibration fit entirely before assessment; artifacts saved before any assessment predictions.',
        'policies':['F1','precision at recall>=20% and>=10validation alerts','balanced accuracy at recall>=20% and>=10alerts'],
        'acceptance':'Minimum20assessment positives,precision>=50%,recall>=20%,accuracy>always-no; useful gate is not a prospective guarantee. Include always-no/yes and past-return heuristics.',
        'status':'Adaptive historical research; data and periods repeatedly inspected. 60-day recorded corrective visit is not formal30-day warranty entitlement. Same recorded return may label multiple earlier windows; no biological recurrence claim.'})
    data,sets,sources=datasets();save(OUT/'source_receipt.json',{'hashes':sources,'feature_sets':sets});results=[];skips=[];support=[];fits=0
    for target,d in data.items():
        test=d[d.anchor_date.between(START,END)].copy();prior=d[d.outcome_end_date.lt(START)].copy();past,_,_=b.purged_split(d,str(START.date()),str((END+pd.Timedelta(days=1)).date()))
        assert not set(past.validation_group)&set(test.validation_group)
        support.append({'target':target,'all_rows':len(d),'assessment_rows':len(test),'assessment_positive':int(test[b.TARGET].sum()),'prior_rows':len(prior)})
        board=[]
        for family,group,window in itertools.product(MODELS,sets,['all','365days']):
            yy=[];pp=[];folds=[]
            for period,a,z in [('2025Q3','2025-07-01','2025-10-01'),('2025Q4','2025-10-01','2026-01-01'),('2026Q1','2026-01-01','2026-04-01')]:
                try:
                    # Source used for selection cannot include still-immature March outcomes.
                    history,valid,_=b.purged_split(prior,a,z)
                    if window=='365days':history=history[history.anchor_date>=pd.Timestamp(a)-pd.Timedelta(days=365)]
                    fit,cal,_=calibration_split(history)
                    if len(valid)<30 or valid[b.TARGET].nunique()<2 or valid[b.TARGET].sum()<3:raise ValueError('Validation support')
                    cols=sets[group];p=classifier(family,cols)
                    with threadpool_limits(limits=2):
                        p.fit(fit[cols],fit[b.TARGET]);raw=p.predict_proba(cal[cols])[:,1];cc,_=b.fit_calibrator(cal[b.TARGET],raw);proba=b.apply_calibrator(cc,p.predict_proba(valid[cols])[:,1])
                    yy.extend(valid[b.TARGET]);pp.extend(proba);folds.append({'period':period,'fit':len(fit),'calibration':len(cal),'validation':len(valid),'positives':int(valid[b.TARGET].sum())});fits+=1
                except ValueError as exc:
                    skips.append({'target':target,'family':family,'features':group,'history':window,'period':period,'reason':str(exc)});continue
            if len(folds)<2:continue
            for cut in THRESHOLDS:board.append({'target':target,'family':family,'features':group,'history':window,'threshold':cut,'fold_support':folds,**score(yy,pp,cut)})
        pd.DataFrame(board).drop(columns='fold_support',errors='ignore').to_csv(OUT/f'{target}_development.csv',index=False)
        selected={p:decision(board,p) for p in ['f1','precision','balanced']};save(OUT/f'{target}_selection.json',selected)
        artifacts={}
        for policy,s in selected.items():
            if s is None:continue
            history=past.copy()
            if s['history']=='365days':history=history[history.anchor_date>=START-pd.Timedelta(days=365)]
            try:fit,cal,_=calibration_split(history)
            except ValueError as exc:skips.append({'target':target,'policy':policy,'reason':'Final '+str(exc)});continue
            cols=sets[s['features']];pipe=classifier(s['family'],cols)
            with threadpool_limits(limits=2):
                pipe.fit(fit[cols],fit[b.TARGET]);cc,_=b.fit_calibrator(cal[b.TARGET],pipe.predict_proba(cal[cols])[:,1])
            # The selected probability cutoff remains frozen from development.
            m={'pipeline':pipe,'calibrator':cc,'threshold':s['threshold'],'features':cols,'frozen_at_utc':datetime.now(timezone.utc).isoformat()};path=OUT/f'{target}_{policy}.joblib';joblib.dump(m,path)
            artifacts[policy]={'file':path.name,'sha256':sha(path),'selection':s,'fit_rows':len(fit),'calibration_rows':len(cal)};fits+=1
        save(OUT/f'{target}_frozen.json',artifacts)
        for policy,item in artifacts.items():
            model=joblib.load(OUT/item['file']);assert sha(OUT/item['file'])==item['sha256']
            with threadpool_limits(limits=2):prob=b.apply_calibrator(model['calibrator'],model['pipeline'].predict_proba(test[model['features']])[:,1])
            met=score(test[b.TARGET],prob,model['threshold']);tn,fp,fn,tp=confusion_matrix(test[b.TARGET],prob>=model['threshold'],labels=[False,True]).ravel()
            heuristic=test.prior_property_warranty_claims.fillna(0).gt(0).astype(float).to_numpy()
            row={'target':target,'policy':policy,'family':item['selection']['family'],'features':item['selection']['features'],'history':item['selection']['history'],'input_count':len(model['features']),
                'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),**met,'always_no_accuracy':float(1-test[b.TARGET].mean()),'past_property_return_heuristic':score(test[b.TARGET],heuristic,.5),
                'passes_research_gate':bool(met['positives']>=20 and met['precision']>=.5 and met['recall']>=.2 and met['accuracy']>1-test[b.TARGET].mean())}
            results.append(row);save(OUT/'results.json',results);pd.DataFrame({'actual':test[b.TARGET].to_numpy(),'probability':prob}).to_csv(OUT/f'{target}_{policy}_assessment.csv',index=False)
        print('Complete target',target,flush=True)
    save(OUT/'skips.json',skips);save(OUT/'support.json',support)
    assert all(sha(ROOT/p)==v for p,v in protected.items())
    save(OUT/'verification.json',{'protected_unchanged':True,'fits':fits,'policies_assessed':len(results),'selection_before_each_target_assessment':True,'independent_prospective':False})
    pd.DataFrame([{k:v for k,v in row.items() if not isinstance(v,dict)} for row in results]).to_csv(OUT/'comparison.csv',index=False)
    print(json.dumps(results,default=str))

if __name__=='__main__':main()
