"""Exploratory prediction of another programme purchase after the final recorded visit.

The target is recorded Sales activity, not verified contract renewal or cash
settlement. No frozen model, prospective receipt or production pointer is edited.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import timedelta
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261030_programme_end_purchase'
CORE=['package_sessions','programme_sales_rm','programme_age_days','prior_programmes',
      'days_as_customer','prior_purchase_average_rm','previous_return_visits',
      'prior_paid_visits','average_paid_visit_gap_days','month_sin','month_cos',
      'premise_type','pest_type','district']
WEATHER=['rain_last_7_days_mm','rain_last_14_days_mm','humidity_last_7_days_pct']

def write(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(value,indent=2,default=str,allow_nan=False),encoding='utf-8')

def build(business,events,programmes,observation_end='2026-10-27'):
    end=pd.Timestamp(observation_end);audit=Counter();owners=defaultdict(set);sales=defaultdict(list)
    for customer in business['customers']:
        if customer['identity_status']=='needs_review':continue
        for sale in customer['sales']:
            if sale.get('date') and pd.Timestamp(sale['date'])<=end:
                # Business exports name ordinary programmes by source row hash;
                # operational facts use the sale ID. Verified pooled programmes
                # retain their explicit UPGRADE_/CONTRACT_ identifiers.
                sale=dict(sale)
                if sale['programme_id'].startswith('SALE_'):
                    sale['programme_id']='SALE_'+sale['sale_id']
                owners[sale['programme_id']].add(customer['customer_key'])
                sales[sale['programme_id']].append(sale)
    programme_lookup={p['programme_id']:p for p in programmes}
    by_customer=defaultdict(list)
    for programme,members in sales.items():
        if len(owners[programme])==1:
            by_customer[next(iter(owners[programme]))].append((programme,min(pd.Timestamp(s['date']) for s in members)))
    by_programme=defaultdict(list)
    for event in events:
        if event.get('programme_id'):by_programme[event['programme_id']].append(event)
    output=[]
    for programme,p in programme_lookup.items():
        audit['programmes_seen']+=1
        if programme not in sales or len(owners[programme])!=1:
            audit['no_unique_customer_and_dated_sale']+=1;continue
        if p['has_cancelled_sale']:
            audit['cancelled_sale']+=1;continue
        n=p.get('effective_paid_sessions')
        if not n or n<1:
            audit['unknown_paid_session_count']+=1;continue
        observed=by_programme[programme]
        paid=[e for e in observed if e['event_category']=='service' and not e['warranty_claim_candidate']]
        finals=[e for e in paid if (e.get('paid_programme_stage')==n or
                (e.get('paid_programme_stage') is None and e.get('session_total')==n and e.get('session_current')==n))]
        if len(finals)!=1:
            audit['missing_or_ambiguous_final_visit']+=1;continue
        final=finals[0];anchor=pd.Timestamp(final['event_date_local'])
        if anchor+pd.Timedelta(days=90)>end:
            audit['outcome_not_mature']+=1;continue
        members=sales[programme];first=min(pd.Timestamp(s['date']) for s in members)
        if max(pd.Timestamp(s['date']) for s in members)>anchor:
            audit['programme_not_fully_purchased_at_anchor']+=1;continue
        customer=next(iter(owners[programme]));other=[(key,day) for key,day in by_customer[customer] if key!=programme]
        if any(first<=day<=anchor for _,day in other):
            audit['another_programme_already_recorded']+=1;continue
        history=[day for _,day in other if day<first]
        historical_sales=[s for key,day in other if day<first for s in sales[key] if pd.Timestamp(s['date'])<anchor]
        visits=[e for e in paid if pd.Timestamp(e['event_date_local'])<anchor]
        days=sorted({pd.Timestamp(e['event_date_local']) for e in visits})
        gaps=[(b-a).days for a,b in zip(days,days[1:])]
        label=int(any(anchor<day<=anchor+pd.Timedelta(days=90) for _,day in other))
        total=lambda items:sum(float(s['sales_rm']) for s in items) if all(s.get('sales_rm') is not None for s in items) else float('nan')
        def category(key):return ' | '.join(sorted({str(s.get(key) or 'Unknown') for s in members}))
        output.append({'customer_group':customer,'programme':programme,'anchor':anchor,
            'outcome_end':anchor+pd.Timedelta(days=90),'label':label,
            'package_sessions':float(n),'programme_sales_rm':total(members),
            'programme_age_days':float((anchor-first).days),'prior_programmes':float(len(history)),
            'days_as_customer':float((anchor-min([first]+history)).days),
            'prior_purchase_average_rm':total(historical_sales)/len(history) if history else 0.,
            'previous_return_visits':float(sum(e['warranty_claim_candidate'] and pd.Timestamp(e['event_date_local'])<anchor for e in observed)),
            'prior_paid_visits':float(len(visits)),
            'average_paid_visit_gap_days':float(np.mean(gaps)) if gaps else 0.,
            'month_sin':float(np.sin(anchor.month*2*np.pi/12)),
            'month_cos':float(np.cos(anchor.month*2*np.pi/12)),
            'premise_type':category('premise'),'pest_type':category('pest'),'district':category('district'),
            'rain_last_7_days_mm':final.get('prior_7d_precipitation_mm'),
            'rain_last_14_days_mm':final.get('prior_14d_precipitation_mm'),
            'humidity_last_7_days_pct':final.get('prior_7d_relative_humidity_mean_pct')})
    result=pd.DataFrame(output).sort_values(['anchor','programme']).reset_index(drop=True) if output else pd.DataFrame()
    audit['eligible_programme_windows']=len(result)
    return result,dict(audit)

def partition(frame):
    """Date-only cutoffs, 90-day maturity gaps and disjoint customer groups."""
    dates=frame['anchor'].sort_values().reset_index(drop=True)
    validation_start=dates.iloc[int(len(dates)*.60)]
    assessment_start=dates.iloc[int(len(dates)*.80)]
    test=frame[frame.anchor>=assessment_start].copy();test_groups=set(test.customer_group)
    validation=frame[(frame.anchor>=validation_start)&(frame.outcome_end<assessment_start)&~frame.customer_group.isin(test_groups)].copy()
    reserved=test_groups|set(validation.customer_group)
    train=frame[(frame.outcome_end<validation_start)&~frame.customer_group.isin(reserved)].copy()
    return train,validation,test,{'cutoff_rule':'60th/80th percentile anchor dates, before reading outcomes',
        'validation_start':str(validation_start.date()),'assessment_start':str(assessment_start.date()),
        'embargo':'Earlier labels must finish before the next partition begins',
        'group_rule':'Test customers removed from all development; validation customers removed from training'}

def train_study(frame):
    import joblib
    from threadpoolctl import threadpool_limits
    from sklearn.base import clone
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline,make_pipeline
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier,HistGradientBoostingClassifier
    from sklearn.metrics import average_precision_score,precision_score,recall_score,f1_score,accuracy_score,brier_score_loss,confusion_matrix,roc_auc_score
    from sklearn.inspection import permutation_importance
    from catboost import CatBoostClassifier
    train,valid,test,protocol=partition(frame)
    assert not (set(train.customer_group)&set(valid.customer_group) or set(train.customer_group)&set(test.customer_group) or set(valid.customer_group)&set(test.customer_group))
    assert train.outcome_end.max()<valid.anchor.min() and valid.outcome_end.max()<test.anchor.min()
    if min(len(train),len(valid),len(test))<30 or min(train.label.sum(),valid.label.sum(),test.label.sum())<2:
        raise ValueError('Insufficient labelled data for even an exploratory comparison')
    seed=20261030
    families={
      'Logistic regression C=0.1':LogisticRegression(C=.1,max_iter=2000,random_state=seed),
      'Balanced logistic regression C=0.1':LogisticRegression(C=.1,class_weight='balanced',max_iter=2000,random_state=seed),
      'Balanced logistic regression C=1':LogisticRegression(C=1,class_weight='balanced',max_iter=2000,random_state=seed),
      'Decision tree depth 3':DecisionTreeClassifier(max_depth=3,min_samples_leaf=15,class_weight='balanced',random_state=seed),
      'Decision tree depth 5':DecisionTreeClassifier(max_depth=5,min_samples_leaf=15,class_weight='balanced',random_state=seed),
      'Random forest':RandomForestClassifier(n_estimators=300,max_depth=8,min_samples_leaf=8,class_weight='balanced_subsample',n_jobs=1,random_state=seed),
      'Extra Trees':ExtraTreesClassifier(n_estimators=300,max_depth=8,min_samples_leaf=8,class_weight='balanced',n_jobs=1,random_state=seed),
      'Gradient boosting':HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=7,min_samples_leaf=15,l2_regularization=10,random_state=seed),
      'CatBoost':CatBoostClassifier(iterations=300,depth=3,learning_rate=.03,l2_leaf_reg=10,auto_class_weights='Balanced',thread_count=1,random_seed=seed,verbose=False,allow_writing_files=False)}
    protocol.update(target='Another distinct recorded programme purchase in the 90 days after final recorded paid visit',
        horizon_days=90,observation_end='2026-10-27',families={k:v.get_params() for k,v in families.items()},
        inputs={'core':CORE,'core_and_weather':CORE+WEATHER},selection='Highest validation average precision; threshold maximises validation F1, ties prefer precision',
        final_fit='Training plus validation; fixed selected configuration and threshold',
        promotion_gate='At least 10 validation and 20 assessment purchase cases, AP above prevalence, precision above prevalence and recall at least 0.4',
        independence='New target on previously examined historical source periods; not an independent prospective test')
    protocol['source_sha256']={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ('business_private.json','events_private.json','programmes_private.json')}
    write('protocol_before_training.json',protocol)
    def metrics(y,prob,threshold):
        pred=np.asarray(prob)>=threshold;tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
        return {'rows':len(y),'positive_cases':int(np.sum(y)),'accuracy':float(accuracy_score(y,pred)),
          'precision':float(precision_score(y,pred,zero_division=0)),'recall':float(recall_score(y,pred,zero_division=0)),
          'f1':float(f1_score(y,pred,zero_division=0)),'average_precision':float(average_precision_score(y,prob)),
          'brier':float(brier_score_loss(y,prob)),'roc_auc':float(roc_auc_score(y,prob)),
          'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}
    candidates=[];models={}
    with threadpool_limits(limits=1):
        for group,features in [('core',CORE),('core_and_weather',CORE+WEATHER)]:
            cats=['premise_type','pest_type','district'];numeric=[f for f in features if f not in cats]
            prep=ColumnTransformer([('numbers',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler()),numeric),
                 ('categories',OneHotEncoder(handle_unknown='ignore',min_frequency=10,sparse_output=False),cats)])
            for name,estimator in families.items():
                model=Pipeline([('prepare',clone(prep)),('model',clone(estimator))]);model.fit(train[features],train.label)
                scores=model.predict_proba(valid[features])[:,1]
                thresholds=[(.5,metrics(valid.label,scores,.5))]+[(float(t),metrics(valid.label,scores,float(t))) for t in np.linspace(.01,.99,99)]
                threshold,measure=max(thresholds,key=lambda v:(v[1]['f1'],v[1]['precision'],v[0]))
                key=name+' / '+group;models[key]=(model,features,threshold)
                candidates.append({'candidate':key,'input_count':len(features),'threshold':threshold,**measure})
                print('Validation complete:',key,flush=True)
        selected=max(candidates,key=lambda r:(r['average_precision'],r['f1'],-r['brier'],r['candidate']))
        write('validation_results.json',candidates);write('selected_before_assessment.json',selected)
        development,features,threshold=models[selected['candidate']]
        effect=permutation_importance(development,valid[features],valid.label,scoring='average_precision',n_repeats=20,random_state=seed,n_jobs=1)
        effects=pd.DataFrame({'input':features,'validation_AP_drop_mean':effect.importances_mean,'validation_AP_drop_sd':effect.importances_std}).sort_values('validation_AP_drop_mean',ascending=False)
        effects.to_csv(OUT/'input_effects.csv',index=False)
        fitted=clone(development);refit=pd.concat([train,valid],ignore_index=True);fitted.fit(refit[features],refit.label)
        joblib.dump({'pipeline':fitted,'features':features,'threshold':threshold,'protocol':protocol},OUT/'experimental_model.joblib')
        prob=fitted.predict_proba(test[features])[:,1];measured=metrics(test.label,prob,threshold)
        pd.DataFrame({'customer_group':test.customer_group,'programme':test.programme,'anchor':test.anchor,'label':test.label,'probability':prob,'prediction':(prob>=threshold).astype(int)}).to_csv(OUT/'assessment_predictions_private.csv',index=False)
    constant=np.full(len(test),float(refit.label.mean()));baselines={'Always no additional purchase':metrics(test.label,constant,1.),
       'Previous programme purchaser':metrics(test.label,(test.prior_programmes>0).astype(float),.5)}
    passing=bool(valid.label.sum()>=10 and test.label.sum()>=20 and measured['average_precision']>test.label.mean() and measured['precision']>test.label.mean() and measured['recall']>=.4)
    result={'selected':selected['candidate'],'raw_inputs':features,'input_count':len(features),'encoded_columns':len(fitted['prepare'].get_feature_names_out()),
            'training_rows':len(train),'validation_rows':len(valid),'final_fit_rows':len(refit),'threshold':threshold,
            'assessment':measured,'baselines':baselines,'passed_promotion_gate':passing,'deployed':False,
            'limitations':[f'Only {int(valid.label.sum())} positive validation cases and {int(test.label.sum())} assessment cases; high uncertainty.',
                'Sales and Calendar are reconstructed from a later snapshot; historical corrections and source vintage are not fully recoverable.',
                'Recorded next programme purchase is not proof of renewing the same contract, settled payment or verified treatment completion.',
                'The historical periods have been inspected previously in other target studies.']}
    write('results.json',result)
    return result

def make_notebook():
    """Build the project chapter with saved results and selected-model replay."""
    import shutil
    import nbformat
    from scripts.build_project_notebooks import notebook
    dest=ROOT/'notebooks/evidence/programme_end_purchase';dest.mkdir(parents=True,exist_ok=True)
    for name in ('results.json','feasibility.json','validation_results.json','input_effects.csv','source_receipt.json','protocol_before_training.json'):
        shutil.copy2(OUT/name,dest/name)
    result=json.loads((OUT/'results.json').read_text())
    sections=[('md','''## Question

At the final recorded paid visit, will the customer have another distinct programme purchase recorded in Sales within 90 days?

One row is one programme-end decision. A purchase already recorded by that date is excluded. Linked upsells remain one programme. Warranty visits are not purchases. Calendar dates describe recorded visits, not verified treatment completion.'''),
    ('code','''E = EVIDENCE / "programme_end_purchase"
result = json.loads((E / "results.json").read_text())
scope = json.loads((E / "feasibility.json").read_text())
validation = pd.read_json(E / "validation_results.json")
display(pd.DataFrame([{"Selected model": result["selected"], "Inputs": result["input_count"],
                       "Encoded columns": result["encoded_columns"], "Deployed": result["deployed"]}]))
'''),
    ('md',f'''## Result

The selected model flagged two cases: one actual buyer and one false warning. It missed 15 of the 16 buyers. Precision is 50%, recall is 6.25%, and accuracy is 95.38% — the same accuracy as always predicting no additional purchase. It is not suitable for deployment.

Only four validation buyers and sixteen test buyers were available. These historical periods were examined in earlier studies; this is a new target experiment, not an independent future test.'''),
    ('md','''## Labelled data

Label 1: another programme starts after the final recorded visit and within the next 90 days. Label 0: no such purchase appears during a complete 90-day observation period. Immature windows and ambiguous identities/final visits are excluded, not labelled zero.

The private working dataset is `outputs/model_validation/20261030_programme_end_purchase/labelled_programmes_private.csv`. Customer and programme keys are used only to join or separate records, never as predictors. The label builder is `scripts/research_programme_end_purchase.py:build`.'''),
    ('code','''display(pd.DataFrame([{"Data check": k.replace("_", " "), "Programme rows": v}
                      for k,v in scope["audit"].items()]))
'''),
    ('md','''## Training, validation and test

Dates were chosen from the 60th and 80th percentiles of eligible anchor dates, without selecting a split by model score. Ninety-day maturity gaps remove unfinished earlier labels. Test customers are excluded from all development; validation customers are excluded from training. Models and thresholds are chosen on validation. Only the selected model is refitted on training plus validation and assessed later.'''),
    ('code','''display(pd.DataFrame([{"Partition": name, **values} for name,values in scope["samples"].items()]))
print("Final selected-model fit:", result["final_fit_rows"], "training + validation rows")
print("Threshold selected from validation:", result["threshold"])
'''),
    ('md','''## Inputs

The first comparison uses 14 customer, programme, location and calendar inputs. The second adds rainfall over the previous 7 and 14 days, and previous-7-day humidity. Both use the same partitions. Unknown Sales amounts remain missing and are imputed from training data. No future weather or future purchase amount is an input.'''),
    ('code','''meaning = {
 "package_sessions": ("Package sessions", "Numerical", "Number of paid sessions in the programme"),
 "programme_sales_rm": ("Programme sales (RM)", "Numerical", "Sales recorded by the prediction date; unknown amounts stay missing"),
 "programme_age_days": ("Days since programme purchase", "Numerical", "Days between the programme purchase and this final visit"),
 "prior_programmes": ("Earlier programmes", "Numerical", "Distinct programmes bought before this programme began"),
 "days_as_customer": ("Days as a customer", "Numerical", "Days since the earliest prior or current purchase"),
 "prior_purchase_average_rm": ("Earlier average programme sales (RM)", "Numerical", "Average sales of earlier programmes, before the current programme"),
 "previous_return_visits": ("Earlier return visits", "Numerical", "Recorded return signals in this programme before this visit"),
 "prior_paid_visits": ("Earlier paid visits", "Numerical", "Recorded normal visits before this final visit"),
 "average_paid_visit_gap_days": ("Average visit gap (days)", "Numerical", "Average spacing between earlier recorded paid visits"),
 "month_sin": ("Month pattern 1", "Numerical / cyclic", "First part of the annual season pattern"),
 "month_cos": ("Month pattern 2", "Numerical / cyclic", "Second part of the same annual season pattern"),
 "premise_type": ("Residential or commercial", "Categorical", "Recorded premise category"),
 "pest_type": ("Pest category", "Categorical", "Recorded pest category of the programme"),
 "district": ("District", "Categorical", "Mapped district; unknown districts remain a category"),
 "rain_last_7_days_mm": ("Rain before visit: 7 days (mm)", "Numerical", "Rainfall total during the preceding seven days"),
 "rain_last_14_days_mm": ("Rain before visit: 14 days (mm)", "Numerical", "Rainfall total during the preceding fourteen days"),
 "humidity_last_7_days_pct": ("Humidity before visit: 7 days (%)", "Numerical", "Average humidity during the preceding seven days")}
display(pd.DataFrame([{"Input":meaning[k][0],"Type":meaning[k][1],"Meaning":meaning[k][2]} for k in result["raw_inputs"]]))
'''),
    ('md','''## Model comparison

Six algorithm families were compared across eighteen configurations. Average precision on validation selected the model. The prediction threshold maximised validation F1. Average precision measures ranking over thresholds; it is not the precision of the final yes/no predictions.'''),
    ('code','''display(validation[["candidate","input_count","average_precision","precision","recall","f1","threshold"]]
        .sort_values("average_precision",ascending=False).round(3))
scores = validation.sort_values("average_precision")
scores["Display model"] = scores["candidate"].str.replace(" / core_and_weather"," + weather",regex=False).str.replace(" / core","",regex=False)
fig, ax = plt.subplots(figsize=(11,8))
ax.barh(scores["Display model"], scores["average_precision"], color="#2563eb")
ax.axvline(scope["samples"]["validation"]["positives"] / scope["samples"]["validation"]["rows"],color="#9a3412",linestyle="--",label="Buyer prevalence")
ax.set(xlabel="Validation average precision",title="Validation comparison — only four positive purchase cases")
ax.legend();fig.tight_layout();plt.show()
'''),
    ('md','''## Selected-model training code

The code below recreates the selected pipeline when the private labelled file is present. It does not repeat model selection, change the threshold, deploy the model or modify the frozen pest-return experiment. A shared copy without private rows can still display the saved aggregate results above and below.'''),
    ('code','''from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
project = BASE.parent
private = project / "outputs/model_validation/20261030_programme_end_purchase/labelled_programmes_private.csv"
if private.exists():
    import sys
    if str(project) not in sys.path: sys.path.insert(0,str(project))
    from scripts.research_programme_end_purchase import partition
    rows = pd.read_csv(private,parse_dates=["anchor","outcome_end"],float_precision="round_trip")
    training, tuning, assessment, _ = partition(rows)
    features = result["raw_inputs"]
    categories = ["premise_type","pest_type","district"]
    numeric = [f for f in features if f not in categories]
    prepare = ColumnTransformer([
        ("numbers",make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),StandardScaler()),numeric),
        ("categories",OneHotEncoder(handle_unknown="ignore",min_frequency=10,sparse_output=False),categories)])
    model = make_pipeline(prepare,LogisticRegression(C=.1,class_weight="balanced",max_iter=2000,random_state=20261030))
    fit_rows = pd.concat([training,tuning],ignore_index=True)
    model.fit(fit_rows[features],fit_rows.label)
    probability = model.predict_proba(assessment[features])[:,1]
    prediction = probability >= result["threshold"]
    replay = confusion_matrix(assessment.label,prediction,labels=[0,1]).ravel().tolist()
    assert replay == [result["assessment"][key] for key in ["tn","fp","fn","tp"]]
    print("Selected model refitted on",len(fit_rows),"rows; saved assessment matrix reproduced.")
else:
    print("Private rows are not included here. Saved aggregate results remain available; refitting needs the private project data.")
'''),
    ('md','''## Test results

Accuracy alone is misleading because only 16 of 346 test examples have another purchase. The selected threshold is 0.99; this value was chosen on the very small validation sample, not on test performance.'''),
    ('code','''a=result["assessment"]
display(pd.DataFrame([{"Model": "Selected model",**a}]+[{"Model":name,**values} for name,values in result["baselines"].items()])
        [["Model","rows","positive_cases","accuracy","precision","recall","f1","tp","fp","fn","tn"]].round(4))
fig, ax = plt.subplots(figsize=(6,4))
matrix=[[a["tn"],a["fp"]],[a["fn"],a["tp"]]]
ax.imshow(matrix,cmap="Blues")
for i in range(2):
    for j in range(2): ax.text(j,i,str(matrix[i][j]),ha="center",va="center",fontsize=20,color="white" if matrix[i][j]>100 else "#172554")
ax.set(xticks=[0,1],xticklabels=["Predict no purchase","Predict purchase"],yticks=[0,1],yticklabels=["No purchase","Purchase recorded"],title="The model missed 15 of 16 actual buyers")
fig.tight_layout();plt.show()
'''),
    ('md','''## Which inputs helped?

This chart shuffles one input at a time in the validation data and measures the decrease in average precision. A larger positive value means the model depended on that input in this small sample. Negative values do not support keeping that input. These are not causal effects or reliable significance tests: the validation set contains only four buyers.'''),
    ('code','''effects=pd.read_csv(E/"input_effects.csv")
effects["Input"]=effects["input"].map(lambda k:meaning[k][0])
display(effects[["Input","validation_AP_drop_mean","validation_AP_drop_sd"]].round(4))
fig,ax=plt.subplots(figsize=(10,6))
view=effects.sort_values("validation_AP_drop_mean")
ax.barh(view["Input"],view["validation_AP_drop_mean"],color=["#2563eb" if v>0 else "#94a3b8" for v in view.validation_AP_drop_mean])
ax.axvline(0,color="#334155",linewidth=1)
ax.set(xlabel="Decrease in validation average precision when shuffled",title="Input importance is unstable with only four validation buyers")
fig.tight_layout();plt.show()
'''),
    ('md','''## Conclusion

This is a genuinely trained new classifier, but it is not a strong replacement or an operationally validated renewal model. It found one buyer and missed fifteen. It failed the predeclared acceptance gate and was not deployed.

Do not replace the frozen pest-return model or call 95.38% accuracy an improvement. Further tests need a different defensible target or better outcome evidence, not a threshold chosen after seeing these test results.

The first pass treated unknown amounts as zero. That pass is retained under `superseded_missing_amount_handling`; the corrected run keeps them missing. Dates, algorithms and selection rules were not changed to select a favourable test score.

Source queries and job IDs are in `evidence/programme_end_purchase/source_receipt.json`. The full search implementation is `scripts/research_programme_end_purchase.py`. Notebook cells were executed sequentially in Python; a native Jupyter kernel is not installed.''')]
    entry=notebook('09_Programme_End_Purchase','Programme-end Purchase Prediction',sections)
    path=ROOT/'notebooks'/entry['file'];nb=nbformat.read(path,as_version=4)
    nb.metadata['cp2']={'scope':'Exploratory new-target experiment and selected-model replay','built':'2026-10-30','native_jupyter_kernel':False}
    nbformat.write(nb,path)
    return entry

if __name__=='__main__':
    b=json.loads((OUT/'business_private.json').read_text(encoding='utf-8'))
    events=json.loads((OUT/'events_private.json').read_text(encoding='utf-8'))
    programmes=json.loads((OUT/'programmes_private.json').read_text(encoding='utf-8'))
    frame,audit=build(b,events,programmes)
    frame.to_csv(OUT/'labelled_programmes_private.csv',index=False)
    train,validation,test,protocol=partition(frame)
    summary={'audit':audit,'partition':protocol,'samples':{name:{'rows':len(d),'customers':d.customer_group.nunique(),'positives':int(d.label.sum()),'first_anchor':str(d.anchor.min().date()) if len(d) else None,'last_anchor':str(d.anchor.max().date()) if len(d) else None} for name,d in [('train',train),('validation',validation),('assessment',test)]}}
    write('feasibility.json',summary);print(json.dumps(summary,indent=2))
    import sys
    if '--train' in sys.argv:print(json.dumps(train_study(frame),indent=2))
