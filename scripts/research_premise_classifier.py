"""Predict a staff-recorded premise category from name/address text only.

This is supervised intake categorisation, not a future-event forecast, verified
property inspection, warranty decision or permission to change source records.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,re,unicodedata
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261030_premise_classifier'

def write(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(value,indent=2,default=str,allow_nan=False),encoding='utf-8')

def clean(text):
    text=unicodedata.normalize('NFKC',str(text or '')).casefold()
    text=re.sub(r'\([^)]*\)',' ',text) # billing/service annotations are not intake evidence
    text=re.sub(r'\b(?:residential|commercial|residence|b2b|b2c|vehicle)\b',' ',text)
    text=re.sub(r'\b[\w.+-]+@[\w.-]+\b|\b\d{9,}\b',' ',text)
    text=re.sub(r'\brm\s*[\d,.]+',' ',text)
    return re.sub(r'\s+',' ',re.sub(r'[^\w\s]',' ',text)).strip()

def dataset(source,business):
    sales={s['sale_id']:s for s in business['records']['sales']};audit=Counter();rows=[]
    for r in source:
        audit['source_rows']+=1
        if not r['include_in_sale_count'] or r['premise_type'] not in ('RESIDENTIAL','COMMERCIAL'):
            audit['other_or_unknown_category']+=1;continue
        day=pd.to_datetime(r.get('closed_date'),errors='coerce')
        if pd.isna(day) or day>pd.Timestamp('2026-10-27'):
            audit['missing_or_incomplete_date']+=1;continue
        name,address=clean(r.get('customer_name_raw')),clean(r.get('address_raw'))
        text=(name+' '+address).strip()
        if len(text)<5:audit['insufficient_text']+=1;continue
        rows.append({'sale_id':r['sales_record_id'],'date':day,'label':int(r['premise_type']=='COMMERCIAL'),
            'name_text':name,'address_text':address,'text':text,'customer_key':sales[r['sales_record_id']]['customer_key'],
            'location':sales[r['sales_record_id']].get('location')})
    # Connected groups prevent identical customers, names, addresses or precise
    # mapped properties from appearing in both development and assessment.
    parent=list(range(len(rows)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    seen={}
    for i,r in enumerate(rows):
        keys=[('customer',r['customer_key'])]
        if len(r['name_text'])>=6:keys.append(('name',r['name_text']))
        if len(r['address_text'])>=20 and re.search(r'\d',r['address_text']):keys.append(('address',r['address_text']))
        loc=r['location']
        if loc and loc.get('uncertainty_km',999)<=.1:
            keys.append(('property',(round(loc['latitude'],4),round(loc['longitude'],4))))
        for key in keys:
            if key in seen:parent[find(i)]=find(seen[key])
            else:seen[key]=i
    for i,r in enumerate(rows):r['group']=hashlib.sha256(('group:'+str(find(i))).encode()).hexdigest();r.pop('location')
    frame=pd.DataFrame(rows).sort_values(['date','sale_id']).reset_index(drop=True)
    if not frame.sale_id.is_unique:raise ValueError('Duplicate Sales join')
    audit['eligible_rows']=len(frame)
    return frame,dict(audit)

def partition(frame):
    dates=frame.date.sort_values().reset_index(drop=True);v=dates.iloc[int(len(dates)*.6)];t=dates.iloc[int(len(dates)*.8)]
    test=frame[frame.date>=t].copy();tg=set(test.group)
    valid=frame[(frame.date>=v)&(frame.date<t)&~frame.group.isin(tg)].copy()
    train=frame[(frame.date<v)&~frame.group.isin(tg|set(valid.group))].copy()
    assert not(set(train.group)&set(valid.group) or set(train.group)&set(test.group) or set(valid.group)&set(test.group))
    return train,valid,test,{'validation_start':str(v.date()),'test_start':str(t.date()),
       'rule':'Date-only 60th/80th percentile cuts, purged connected customer/name/address/property groups'}

def keyword(text):
    return int(bool(re.search(r'\b(?:sdn|bhd|restoran|restaurant|kedai|cafe|kopitiam|trading|enterprise|office|shop|hotel|school|tadika|pasti|surau|masjid|warehouse|studio|clinic|klinik|bakery|dobi|laundry)\b',text)))

def measure(y,prob):
    from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score,confusion_matrix,balanced_accuracy_score,average_precision_score,brier_score_loss
    pred=np.asarray(prob)>=.5;tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return {'rows':len(y),'commercial_cases':int(np.sum(y)),'accuracy':float(accuracy_score(y,pred)),
       'balanced_accuracy':float(balanced_accuracy_score(y,pred)),'macro_f1':float(f1_score(y,pred,average='macro')),
       'commercial_precision':float(precision_score(y,pred,zero_division=0)),'commercial_recall':float(recall_score(y,pred,zero_division=0)),
       'residential_precision':float(precision_score(y,pred,pos_label=0,zero_division=0)),'residential_recall':float(recall_score(y,pred,pos_label=0,zero_division=0)),
       'average_precision':float(average_precision_score(y,prob)),'brier':float(brier_score_loss(y,prob)),
       'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}

def study(frame):
    import joblib
    from threadpoolctl import threadpool_limits
    from sklearn.base import clone
    from sklearn.pipeline import FeatureUnion,make_pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.naive_bayes import ComplementNB
    train,valid,test,split=partition(frame);seed=20261030
    families={'Logistic C=0.1':LogisticRegression(C=.1,max_iter=2000,random_state=seed),
        'Logistic C=1':LogisticRegression(C=1,max_iter=2000,random_state=seed),
        'Logistic C=10':LogisticRegression(C=10,max_iter=2000,random_state=seed),
        'Balanced logistic C=1':LogisticRegression(C=1,class_weight='balanced',max_iter=2000,random_state=seed),
        'Complement NB alpha=0.1':ComplementNB(alpha=.1),'Complement NB alpha=1':ComplementNB(alpha=1)}
    protocol={'target':'Staff-recorded COMMERCIAL versus RESIDENTIAL premise category','scope':'Intake categorisation, not future events or verified eligibility',
      'inputs':['Customer name','Customer address'],'excluded':['Premise field itself','Sales amounts','Package','Pest','Payments','IDs','Parenthetical notes','Explicit category words'],
      'split':split,'features':['Word 1–2 grams','Word 1–2 plus character 3–5 grams'],'selection':'Highest validation macro F1; fixed 0.5 threshold',
      'families':{k:v.get_params() for k,v in families.items()},
      'acceptance':'Accuracy >=90%, macro F1 >=85%, both class precision >=85%, and positive lower 95% customer/property bootstrap accuracy improvement over keyword baseline',
      'source_sha256':hashlib.sha256((OUT/'source_private.json').read_bytes()).hexdigest(),
      'limitations':'Historic name/address edits and manually recorded category errors are not fully recoverable. No independent future intake test.'}
    write('protocol_before_training.json',protocol);scores=[];models={}
    with threadpool_limits(limits=1):
        for kind in ('words','words_and_characters'):
            words=TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=20000,sublinear_tf=True)
            features=words if kind=='words' else FeatureUnion([('words',words),('characters',TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,max_features=30000,sublinear_tf=True))])
            for name,estimator in families.items():
                model=make_pipeline(clone(features),clone(estimator));model.fit(train.text,train.label)
                measured=measure(valid.label,model.predict_proba(valid.text)[:,1]);key=name+' / '+kind
                scores.append({'candidate':key,**measured});models[key]=model;print('Validation',key,round(measured['macro_f1'],3),flush=True)
        selected=max(scores,key=lambda r:(r['macro_f1'],r['balanced_accuracy'],-r['brier'],r['candidate']))
        write('validation_results.json',scores);write('selected_before_test.json',selected)
        final=clone(models[selected['candidate']]);refit=pd.concat([train,valid],ignore_index=True);final.fit(refit.text,refit.label)
        prob=final.predict_proba(test.text)[:,1];pred=prob>=.5;baseline=np.array([keyword(t) for t in test.text])
        joblib.dump({'pipeline':final,'protocol':protocol,'threshold':.5},OUT/'experimental_model.joblib')
    result=measure(test.label,prob);base=measure(test.label,baseline)
    majority=measure(test.label,np.full(len(test),int(refit.label.mean()>=.5)))
    pd.DataFrame({'sale_id':test.sale_id,'group':test.group,'label':test.label,'probability_commercial':prob,'prediction':pred.astype(int),'keyword_prediction':baseline}).to_csv(OUT/'test_predictions_private.csv',index=False)
    groups=test.group.to_numpy();unique=np.unique(groups);delta=(pred==test.label.to_numpy()).astype(int)-(baseline==test.label.to_numpy()).astype(int)
    sums=np.array([delta[groups==g].sum() for g in unique]);sizes=np.array([(groups==g).sum() for g in unique]);rng=np.random.default_rng(seed);boot=[]
    for _ in range(1000):idx=rng.integers(0,len(unique),len(unique));boot.append(float(sums[idx].sum()/sizes[idx].sum()))
    ci=[float(x) for x in np.quantile(boot,[.025,.975])]
    high=np.maximum(prob,1-prob)>=.9
    passing=bool(result['accuracy']>=.9 and result['macro_f1']>=.85 and min(result['commercial_precision'],result['residential_precision'])>=.85 and ci[0]>0)
    feature_count=final[0].transform(refit.text.iloc[:1]).shape[1]
    output={'selected':selected['candidate'],'raw_inputs':2,'encoded_features':feature_count,'training_rows':len(train),'validation_rows':len(valid),'test_rows':len(test),'final_fit_rows':len(refit),
       'test':result,'keyword_baseline':base,'majority_baseline':majority,'bootstrap_accuracy_improvement_95':ci,
       'score_at_least_0_9':{'rows':int(high.sum()),'coverage':float(high.mean()),'accuracy':float(np.mean(pred[high]==test.label.to_numpy()[high])) if high.any() else None},
       'passed_research_gate':passing,'deployed':False,
       'limitations':['Only residential/commercial labels are modelled; vehicles and unknown labels are excluded.',
        'Labels are staff-recorded categories, not independently inspected building use.',
        'Historical source text may have been corrected after intake; point-in-time availability is not fully proven.',
        'This is classification of supplied information, not prediction of future warranty claims or renewals.',
        'Suggestions must be reviewed; never use the classifier alone to grant or deny warranty.']}
    write('results.json',output);return output

def prepare():
    source=json.loads((OUT/'source_private.json').read_text(encoding='utf-8'))
    b=json.loads((ROOT/'outputs/model_validation/20261030_programme_end_purchase/business_private.json').read_text(encoding='utf-8'))
    frame,audit=dataset(source,b);frame.to_csv(OUT/'labelled_text_private.csv',index=False)
    train,valid,test,split=partition(frame)
    info={'audit':audit,'split':split,'samples':{name:{'rows':len(d),'groups':d.group.nunique(),'commercial':int(d.label.sum()),'residential':int((d.label==0).sum()),'from':str(d.date.min().date()),'to':str(d.date.max().date())} for name,d in [('training',train),('validation',valid),('test',test)]}}
    write('feasibility.json',info);return frame,info

if __name__=='__main__':
    import sys
    frame,info=prepare();print(json.dumps(info,indent=2),flush=True)
    if '--train' in sys.argv:print(json.dumps(study(frame),indent=2))
