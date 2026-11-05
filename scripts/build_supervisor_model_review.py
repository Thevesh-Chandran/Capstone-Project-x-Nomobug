"""Build an aggregate-only, executed supervisor notebook from pinned model sources.

No training, threshold changes, live queries, private row exports or deployment.
"""
from pathlib import Path
import base64,contextlib,hashlib,html,io,json,re,sys,zipfile
import numpy as np
import pandas as pd
import nbformat
from scipy.stats import chi2_contingency
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/supervisor_model_review/20261017'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def group(name):
    if name.startswith(('prior_property','prior_package','prior_area','days_since_prior','first_service_no_property','first_service_prior','mixed_pest_prior')):return 'Past recorded pest/service history'
    if name.startswith(('hotosm','elevation','local_relief','nearest_mapped','log1p_waterway')):return 'Geographic environment'
    if name.startswith(('prior_1d','prior_3d','prior_7d','prior_14d','prior_30d','days_since_last_rain')):return 'Weather before service'
    if name in ('water_rain_interaction','drainage_rain_interaction','rain_soil_interaction','mixed_pest_rain_14d','first_service_rain_14d'):return 'Derived weather interactions'
    if 'pest' in name:return 'Pest category and indicators'
    return 'Service, package and premises'

def associations(frame,features,target):
    records=[]
    for name in features:
        x=frame[name];y=frame[target].astype(int)
        if pd.api.types.is_numeric_dtype(x):
            valid=x.notna()&np.isfinite(x)
            x,y=x[valid],y[valid]
            good=len(x)>2 and x.nunique()>1 and y.nunique()>1
            records.append({'feature':name,'group':group(name),'available_rows':len(x),'missing_pct':100*(1-len(x)/len(frame)),
                'pearson_r':x.corr(y) if good else np.nan,'spearman_rho':x.corr(y,method='spearman') if good else np.nan})
    return pd.DataFrame(records)

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'data').mkdir(exist_ok=True)
    bundle_path=ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json'
    bundle=json.loads(bundle_path.read_text());source=ROOT/Path(bundle['training_input_relative_path'])
    assert sha(source)==bundle['input_file_sha256']
    import joblib
    artifact_path=bundle_path.parent/bundle['models']['challenger_all_history']['file']
    assert sha(artifact_path)==bundle['models']['challenger_all_history']['sha256']
    encoded_columns=int(joblib.load(artifact_path)['members'][0]['pipeline'].named_steps['classifier'].n_features_in_)
    frame=c.prepare_input(b.load_dataset_input(source));features=bundle['models']['challenger_all_history']['features']
    cutoff=pd.Timestamp('2026-08-15');dev=frame[frame.outcome_end_date<cutoff].copy();hold=frame[frame.anchor_date>=cutoff]
    assert len(frame)==5695 and len(dev)==5333 and len(hold)==100
    assert dev[b.TARGET].isin([False,True]).all()
    numeric=associations(dev,features,b.TARGET);numeric.to_csv(OUT/'data/numeric_associations.csv',index=False)
    dictionary=pd.DataFrame([{'predictor':name,'group':group(name),'type':'categorical' if name in b.CATEGORICAL else ('binary indicator' if set(dev[name].dropna().unique())<={0,1} else 'numerical'),
        'missing_pct':100*dev[name].isna().mean(),'available_before_prediction':'Required; historical availability not independently proven for every field'} for name in features])
    descriptions={'service_number':'Recorded paid stage within the programme; not independent proof of completed treatment','package_sessions_recorded':'Recorded planned paid services in the linked package','sale_total_rm':'Recorded package price, not cash received or profit','prior_property_warranty_claims':'Prior recorded corrective return visits linked to the property','prior_property_service_events':'Prior recorded service events linked to the property','prior_property_return_rate_smoothed':'(prior property returns + 1) / (prior property service events + 10); not a literal measured infestation rate','prior_package_return_rate_smoothed':'(prior package returns + 1) / (prior package service events + 10)','prior_area_claims_90d':'Prior recorded local-area corrective returns in the 90-day lookback; depends on service coverage','prior_area_services_90d':'Prior recorded local-area service exposure in the 90-day lookback','days_since_prior_property_claim':'Elapsed time since the prior recorded property return','anchor_remaining_services':'Recorded package sessions minus current paid stage','anchor_service_progress':'Current recorded paid stage divided by recorded package sessions','location_uncertainty_radius_m':'Estimated geolocation uncertainty; not pest exposure','premise_type':'Recorded residential/commercial context','normalized_pest_category':'Normalised Calendar pest text, including mixed/unknown categories'}
    dictionary['description']=[descriptions.get(name,name.replace('_',' ')+'; derived/observed at the prediction anchor according to the feature contract') for name in dictionary.predictor]
    dictionary.to_csv(OUT/'data/predictor_dictionary.csv',index=False)
    categories=[];category_summary=[]
    for name in ['premise_type','package_sessions_recorded','normalized_pest_category']:
        x=dev[name].fillna('Unknown').astype(str);frequent=set(x.value_counts()[lambda s:s>=20].index);x=x.where(x.isin(frequent),'Other / fewer than 20 services')
        contingency=pd.crosstab(x,dev[b.TARGET]);chi=chi2_contingency(contingency,correction=False)[0];v=np.sqrt(chi/(contingency.to_numpy().sum()*min(contingency.shape[0]-1,contingency.shape[1]-1)))
        category_summary.append({'predictor':name,'cramers_v':v,'services':len(dev),'grouping':'Groups below 20 combined; descriptive, uncorrected V'})
        for value,part in dev.groupby(x):categories.append({'predictor':name,'category':value,'services':len(part),'recorded_returns':int(part[b.TARGET].sum()),'return_rate':part[b.TARGET].mean()})
    pd.DataFrame(categories).to_csv(OUT/'data/category_rates.csv',index=False);pd.DataFrame(category_summary).to_csv(OUT/'data/category_associations.csv',index=False)
    chosen=['service_number','package_sessions_recorded','prior_property_service_events','prior_property_warranty_claims','prior_property_return_rate_smoothed','prior_area_claims_90d','prior_14d_precipitation_mm','prior_7d_temperature_mean_c','prior_7d_relative_humidity_mean_pct','hotosm_nearest_waterway_m','hotosm_nearest_drainage_m','elevation_m']
    dev[chosen].corr(method='spearman').to_csv(OUT/'data/predictor_correlations.csv')
    rates=[]
    for name in ['prior_property_return_rate_smoothed','prior_14d_precipitation_mm','service_number']:
        available=dev[dev[name].notna()];bins=pd.qcut(available[name],4,duplicates='drop')
        for interval,part in available.groupby(bins,observed=True):rates.append({'predictor':name,'band':str(interval),'services':len(part),'returns':int(part[b.TARGET].sum()),'rate':part[b.TARGET].mean()})
    pd.DataFrame(rates).to_csv(OUT/'data/predictor_band_rates.csv',index=False)
    splits=[]
    for name,start,end in b.DEVELOPMENT_FOLDS:
        train,test,audit=b.purged_split(dev,start,end)
        splits.append({'period':name,'validation_start':start,'validation_end_exclusive':end,'fit_services':len(train),'validation_services':len(test),'validation_returns':int(test[b.TARGET].sum()),**audit})
    pd.DataFrame(splits).to_csv(OUT/'data/development_partitions.csv',index=False)
    observation=pd.to_datetime(frame.observed_through);weather=pd.to_datetime(frame.latest_weather_date_used,errors='coerce')
    meta={'created_local':'2026-10-17','scope':'Archived frozen-refit source; not a fresh Calendar audit or new final evaluation',
        'total_refit_services':len(frame),'total_refit_returns':int(frame[b.TARGET].sum()),'eda_services':len(dev),'eda_returns':int(dev[b.TARGET].sum()),
        'holdout_services':len(hold),'holdout_returns':int(hold[b.TARGET].sum()),'maturity_gap_services':len(frame)-len(dev)-len(hold),
        'shared_development_holdout_groups':len(set(dev.validation_group)&set(hold.validation_group)),
        'raw_predictors':len(features),'encoded_columns':encoded_columns,
        'checks':{'unresolved_labels':int(frame[b.TARGET].isna().sum()),'duplicate_service_keys':int(frame.duplicated(c.KEYS).sum()),'non_30_day_windows':int(((frame.outcome_end_date-frame.anchor_date).dt.days!=30).sum()),'outcomes_after_observation':int((frame.outcome_end_date>observation).sum()),'weather_on_or_after_service':int((weather>=frame.anchor_date).sum()),'weather_latest_date_missing':int(weather.isna().sum())},
        'sources':{'training_input':{'path':str(source.relative_to(ROOT)).replace('\\','/'),'sha256':sha(source)},'bundle':{'path':str(bundle_path.relative_to(ROOT)).replace('\\','/'),'sha256':sha(bundle_path)},'artifact':{'path':str(artifact_path.relative_to(ROOT)).replace('\\','/'),'sha256':sha(artifact_path)},'earlier_holdout':{'path':'config/warranty_new_holdout_v5.json','sha256':sha(ROOT/'config/warranty_new_holdout_v5.json')},'research_candidate':{'path':'webapp/models/return_research_best.json','sha256':sha(ROOT/'webapp/models/return_research_best.json')}},
        'building_age_available':False,'correlation_scope':'Development rows with outcomes ending strictly before 15 August 2026; observed non-missing pairs; not independent causal effects'}
    (OUT/'data/review_metadata.json').write_text(json.dumps(meta,indent=2))
    result30=json.loads((ROOT/'config/warranty_new_holdout_v5.json').read_text())['results']['selected_ap']['metrics']
    result60=json.loads((ROOT/'webapp/models/return_research_best.json').read_text())['candidate']
    history=list(b.FEATURE_SETS['base'])
    service_features=[x for x in history if not x.startswith('prior_') and x not in ['days_since_previous_service','days_since_prior_property_claim']]+list(b.CATEGORICAL)
    pd.DataFrame({'research60_predictor':service_features,'type':['categorical' if x in b.CATEGORICAL else 'numerical / binary' for x in service_features]}).to_csv(OUT/'data/research60_predictors.csv',index=False)
    research_partitions=[]
    fold_source=ROOT/'outputs/model_validation/20261016_target_research/fold_metrics.jsonl'
    for line in fold_source.read_text().splitlines():
        row=json.loads(line)
        if all(row[k]==result60[k] for k in ['horizon','target','population','features','model']):
            research_partitions.append({k:row[k] for k in ['fold','fit_rows','calibration_rows','calibration_positives','rows','positives','threshold']})
    assert sum(r['rows'] for r in research_partitions)==result60['services']
    assert sum(r['positives'] for r in research_partitions)==result60['positive_windows']
    pd.DataFrame(research_partitions).to_csv(OUT/'data/research60_partitions.csv',index=False)
    meta['sources']['research60_folds']={'path':str(fold_source.relative_to(ROOT)).replace('\\','/'),'sha256':sha(fold_source)}
    (OUT/'data/review_metadata.json').write_text(json.dumps(meta,indent=2))
    (OUT/'data/model_results.json').write_text(json.dumps({'return30':result30,'research60':result60},indent=2))
    pd.DataFrame(columns=['anonymous_review_key','service_stage','anchor_date','outcome_end_date','dataset_label','linked_return_date_if_any','window_fully_observed','cancelled_or_placeholder','programme_link_verified','independent_evidence_type','reviewed_label_0_1_or_unknown','review_reason','reviewer_date']).to_csv(OUT/'data/label_audit_template.csv',index=False)
    pd.DataFrame([
        ['building_id','categorical identifier','Verified building registry; separate units consistently','Not available as a verified building-wide identifier'],
        ['year_built_or_age_band','numeric year or ordered band','Owner/documented construction record; preserve source','Proposed; do not guess from address'],
        ['age_source_and_verified_at','text and timestamp','Record who supplied it and when it was known','Proposed'],
        ['prior_pest_report_date','date','Dated technician/client/external report','Proposed external history; existing recorded returns are a proxy'],
        ['pest_type_and_severity','categorical and defined ordinal scale','Technician assessment with an agreed severity rubric','Severity is not currently a verified predictor'],
        ['report_known_at','timestamp','Time when the report was available to the business','Must precede prediction; needed to prevent hindsight leakage']
    ],columns=['proposed_field','type','collection_rule','current_status']).to_csv(OUT/'data/proposed_building_predictors.csv',index=False)
    # Do not hash the previous manifest into itself on regeneration.
    manifest={p.name:sha(p) for p in sorted((OUT/'data').iterdir()) if p.name!='manifest.json'};(OUT/'data/manifest.json').write_text(json.dumps(manifest,indent=2))
    cells=[]
    def md(t):cells.append(nbformat.v4.new_markdown_cell(t))
    def code(t):cells.append(nbformat.v4.new_code_cell(t))
    md('# CP2 model review for supervisor\n17 October 2026 · predictors, labels, relationships and validation\n\n## Summary\nThe model predicts a **recorded pest-related return visit within 30 days after a paid service**. The label is based on Calendar records, not independently verified pest recurrence or a formal warranty claim. The archived refit contains **5,695 services and 521 positive windows**. Predictor exploration below uses **5,333 earlier services with 492 positives** only.\n\nThe main issues are weak outcome verification, sparse positive outcomes in the earlier 100-service test, historical source revisions, and unproven future reliability. Building age is not available. Past property pest-return history is available, subject to matching and recording limits. No model is retrained by this notebook.')
    md('## Context and methods\nThis is an evidence review, not a new model-selection experiment. Associations are descriptive: they do not prove causality, independent predictor usefulness or future accuracy. The data contain repeated services at the same property and overlapping outcome windows. No ordinary independence-based significance claims are made.\n\n### Reproducibility and privacy\nThis share folder contains aggregate analysis tables, their SHA256 hashes, editable plotting code and saved outputs. It contains **no customer-level modelling rows, identifiers, addresses, names, credentials or individual predictions**. Full source regeneration uses `scripts/build_supervisor_model_review.py` inside the private project; the source path and hash are recorded. Rerunning this notebook reproduces the aggregate review, not the unavailable private extraction. All cells were executed sequentially in Python and notebook format validated; this environment has no Jupyter kernel installed.')
    code("from pathlib import Path\nimport json, hashlib\nimport pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\nBASE=Path.cwd()\nif not (BASE/'data/manifest.json').exists():\n    BASE=BASE/'outputs/supervisor_model_review/20261017'\nassert (BASE/'data/manifest.json').exists(), 'Run from the shared review folder or project root.'\nfor name, expected in json.loads((BASE/'data/manifest.json').read_text()).items():\n    assert hashlib.sha256((BASE/'data'/name).read_bytes()).hexdigest()==expected, name\nmeta=json.loads((BASE/'data/review_metadata.json').read_text())\nplt.rcParams.update({'figure.dpi':130,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})\nprint('All aggregate inputs match their recorded hashes.')")
    md('## Data and labels\nOne row represents one recorded paid-service anchor, not one unique customer or one unique pest event. `y = 1` means at least one linked corrective/return visit occurs strictly after the anchor and within 30 days, including day 30. `y = 0` means no linked return is recorded during a completely observed 30-day window. Missing or immature outcomes must not be relabelled zero.\n\nA single return can label several overlapping earlier service windows positive. A scheduled Calendar visit is not proof of treatment completion. Postponed/cancelled placeholders and programme links need source review; the notebook audits a pinned historical export, not every current source correction.\n\nResidential 3x warranty ends 30 days after the actual third paid service, even if rescheduled beyond 14 days. Commercial corrective returns can exist despite no warranty entitlement. Therefore the current all-service target must not be renamed “approved warranty claim”.')
    code("display(pd.DataFrame({'label':['0: no recorded return','1: recorded return'], 'refit_services':[meta['total_refit_services']-meta['total_refit_returns'],meta['total_refit_returns']], 'earlier_EDA_services':[meta['eda_services']-meta['eda_returns'],meta['eda_returns']]}))\nfig,ax=plt.subplots(figsize=(7,3))\nax.barh(['No recorded return','Recorded return'],[meta['eda_services']-meta['eda_returns'],meta['eda_returns']],color=['#94a3b8','#2563eb'])\nax.set_xlabel('Earlier labelled service windows');ax.set_title('Label imbalance in predictor-exploration data')\nplt.tight_layout();plt.show()")
    code("display(pd.DataFrame(list(meta['checks'].items()),columns=['Archived data check','Rows']))\nassert all(meta['checks'][k]==0 for k in ['unresolved_labels','duplicate_service_keys','non_30_day_windows','outcomes_after_observation','weather_on_or_after_service'])\nprint('These structural checks do not independently verify whether every return was recorded or every historical predictor was available at scoring time.')\nprint('Rows without a latest-weather date:',meta['checks']['weather_latest_date_missing'],'; their weather timing cannot be independently checked from that field.')")
    md('## Predictors currently used\nThe frozen Extra Trees model uses **93 input predictors** and **238 transformed columns** after imputation and categorical encoding. These are feature counts, not the number of learned tree parameters. Numerical predictors include elapsed days, prior counts, rain, humidity and distance. Categorical predictors include premises, package and pest categories. Binary predictors flag pest types and service stages. Month is represented by sine/cosine to preserve seasonality.\n\nMissing numeric values are handled inside the training pipeline; categorical values are encoded. Building age, year built, verified building-wide pest severity and a complete external building pest history are not included. Geographic water/drainage distances do not by themselves measure actual flooding or building condition.')
    code("dictionary=pd.read_csv(BASE/'data/predictor_dictionary.csv')\ndisplay(dictionary.groupby(['group','type'],as_index=False).size().rename(columns={'size':'predictors'}))\nfig,ax=plt.subplots(figsize=(9,4))\ncounts=dictionary.groupby('group').size().sort_values()\nax.barh(counts.index,counts.values,color='#2563eb');ax.set_xlabel('Input predictors');ax.set_title('What information the frozen model uses')\nplt.tight_layout();plt.show()\ndisplay(dictionary[['predictor','type','missing_pct']].sort_values('missing_pct',ascending=False).head(12).round(2))")
    md('The full dictionary is in `data/predictor_dictionary.csv`. Predictors with substantial missingness need a coverage explanation before their relationship is interpreted. Previous return counts measure **recorded return history**, not a technician-verified infestation score. Property history follows the project property identifier; that is not yet a verified building registry covering all units.')
    md('## Relationships with the outcome\nFor numerical/binary fields, Pearson correlation with a 0/1 outcome is the point-biserial correlation. Spearman correlation compares ranks and can show a monotonic association. Values near zero indicate weak association under that measure; they do not rule out nonlinear interactions. Missing pairs are excluded, so each predictor has its own denominator. No missing weather is converted to zero for this analysis.\n\nThe association code uses `x.corr(y)` and `x.corr(y, method="spearman")` on earlier observed pairs. Features are not selected from this chart, and the final test is not retuned.')
    code("association=pd.read_csv(BASE/'data/numeric_associations.csv')\nranked=association.dropna(subset=['spearman_rho']).assign(strength=lambda d:d.spearman_rho.abs()).sort_values('strength',ascending=False)\ndisplay(ranked[['feature','available_rows','missing_pct','pearson_r','spearman_rho']].head(15).round(3))\nfig,ax=plt.subplots(figsize=(10,6))\nshown=ranked.head(15).iloc[::-1]\nax.barh(shown.feature,shown.spearman_rho,color=np.where(shown.spearman_rho>=0,'#2563eb','#f59e0b'))\nax.axvline(0,color='#64748b',linewidth=.7);ax.set_xlim(-1,1);ax.set_xlabel('Spearman correlation with recorded return (−1 to +1)');ax.set_title('Largest observed associations · earlier development data')\nplt.tight_layout();plt.show()\nprint('Descriptive associations, not causal effects or out-of-sample feature importance.')")
    md('### Interpretation of this check\nThe strongest numerical associations are service-stage features, with absolute Spearman values around 0.22. The 14-day rainfall value is about 0.014, prior area returns about 0.030, and prior property return count about 0.004. These are weak bivariate associations in this archived development sample. They do not establish a useful rainfall predictor.\n\nThe smoothed property return rate has a negative association (about −0.181). Its formula is `(past returns + 1) / (past services + 10)`: even with no past returns, more past services reduce the value. This can entangle service progression and observation exposure. It must not be interpreted as evidence that past infestations protect a building. Check denominator effects and same-cohort feature ablations before using it as an explanation.')
    md('### Categorical predictors\nA category name does not have a meaningful numerical order. Cramér’s V measures association between category and outcome; it has no positive/negative direction. The displayed V is an uncorrected descriptive measure and can be inflated by many categories. Categories with fewer than 20 services are combined for this review; this grouping is for reporting, not a model change.')
    code("display(pd.read_csv(BASE/'data/category_associations.csv').round(3))\ncategory_rates=pd.read_csv(BASE/'data/category_rates.csv')\nshown=category_rates[category_rates.predictor=='package_sessions_recorded'].sort_values('services',ascending=False)\ndisplay(shown.round(3))\nfig,ax=plt.subplots(figsize=(9,3.6))\nax.bar(shown.category.astype(str),100*shown.return_rate,color='#7c3aed');ax.set_ylabel('Recorded return rate (%)');ax.set_ylim(0,100);ax.set_xlabel('Recorded package sessions / combined small categories')\nax.set_title('Observed return rates differ by package · no causal conclusion')\nplt.xticks(rotation=20,ha='right');plt.tight_layout();plt.show()")
    md('### Predictor overlap\nSeveral history and weather fields measure related things. This heatmap helps identify redundancy; high correlation is not a reason to remove a feature automatically. Any simplification must be assessed on earlier training/validation periods, then frozen before a future test.')
    code("correlations=pd.read_csv(BASE/'data/predictor_correlations.csv',index_col=0)\nlabels=[s.replace('prior_','').replace('hotosm_','').replace('_',' ') for s in correlations.index]\nfig,ax=plt.subplots(figsize=(10,8))\nim=ax.imshow(correlations,cmap='coolwarm',vmin=-1,vmax=1);ax.set_xticks(range(len(labels)),labels,rotation=90,fontsize=8);ax.set_yticks(range(len(labels)),labels,fontsize=8);fig.colorbar(im,ax=ax,label='Spearman correlation');ax.set_title('Related predictors · pairwise observed values')\nplt.tight_layout();plt.show()")
    md('### Inspect actual rates, not correlation alone\nThe following bands are formed from earlier data only. Ties can reduce the number of quantile bands. Band membership is descriptive; these are not deployed thresholds. Counts refer to service windows, which are not independent unique buildings.')
    code("bands=pd.read_csv(BASE/'data/predictor_band_rates.csv')\ndisplay(bands.round(3))\nfig,axes=plt.subplots(1,3,figsize=(12,4))\nfor ax,(name,part) in zip(axes,bands.groupby('predictor',sort=False)):\n    ax.bar(range(len(part)),100*part.rate,color='#0891b2');ax.set_xticks(range(len(part)),['Band '+str(i+1)+'\\nn='+str(n) for i,n in enumerate(part.services)],fontsize=8);ax.set_ylim(0,100);ax.set_title(name.replace('prior_','').replace('_',' '),fontsize=10);ax.set_ylabel('Recorded return rate (%)')\nplt.tight_layout();plt.show()")
    md('## Partition: training, validation and test\nThe historical process is chronological, not “choose whichever random percentage gives the highest accuracy”. Earlier development folds train on mature past labels and remove connected property/package groups appearing in the validation period. Imputation, encoding, calibration and threshold selection must be fitted using the allowed earlier data.\n\nThe earlier 100-service holdout is a **later-date test**, not a claim of completely unseen properties: **34 connected groups** overlap the earlier development population. The model used for that evaluation had 5,333 fitting services with outcomes ending before 15 August. The later prospective model was then refitted on all 5,695 mature services, including those 100; its future accuracy cannot be measured by testing it again on them.\n\nThe 262 intervening rows are service windows crossing the historical fitting cutoff; they are not silently counted as an independent test. The fold table below is recomputed from the pinned source and split function. It documents the source epoch, not a newly trained model.')
    code("display(pd.read_csv(BASE/'data/development_partitions.csv'))\ndisplay(pd.DataFrame({'historical_partition':['Mature fitting data before 15 Aug','Intervening maturity-gap rows','Later test: 15–27 Aug'], 'services':[meta['eda_services'],meta['maturity_gap_services'],meta['holdout_services']]}))\nprint('Refit total:',meta['total_refit_services'],'; earlier/later shared groups:',meta['shared_development_holdout_groups'])\nprint('A new prospective cohort is separate. Its scheduled full outcome review is 30 November 2026, subject to collection and complete-outcome checks.')")
    md('## Results and the separate 60-day question\nAccuracy alone can reward always predicting no return when positives are rare. Recall measures returns caught; precision measures how many alerts were correct. Brier score is squared probability error; lower is better. The 60-day candidate below was selected after comparing historical results and is research only. Its different population and outcome horizon prevent a fair direct “better accuracy” claim.')
    md('### Predictors and partition for the 60-day research candidate\nThe selected logistic-regression candidate uses the **service block: 23 input fields**, including service/package counts, sale price, elapsed days from sale, month, geolocation uncertainty, pest indicators and six categorical fields. **It does not use building age, the past-history block or weather.** Its feature block should not be confused with the frozen model’s 93 predictors.\n\nThe 937 evaluated programmes come from four chronological, property-purged outer periods. Within each, separate earlier fitting and calibration rows set probabilities and a decision threshold. The table below gives their actual counts and thresholds from saved fold metrics. This is a different archived source epoch (5,598 original service anchors, observed through 13 September 2026). The earlier correlation charts are for the 30-day development dataset and must not be presented as 60-day feature evidence.')
    code("display(pd.read_csv(BASE/'data/research60_predictors.csv'))\nresearch_partitions=pd.read_csv(BASE/'data/research60_partitions.csv')\ndisplay(research_partitions.round(3))\nassert research_partitions.rows.sum()==937\nassert research_partitions.positives.sum()==319")
    code("results=json.loads((BASE/'data/model_results.json').read_text());a=results['return30'];z=results['research60']\ndisplay(pd.DataFrame([{'question':'30-day return after each paid service','model':'Extra Trees: earlier candidate test','tested':a['rows'],'positive':a['positives'],'accuracy':a['accuracy'],'no_return_baseline':a['majority_class_accuracy'],'recall':a['recall'],'precision':a['precision'],'F1':a['f1'],'Brier':a['brier_score']},{'question':'60-day return after final residential service','model':'Logistic regression: searched research candidate','tested':z['services'],'positive':z['positive_windows'],'accuracy':z['pooled_accuracy'],'no_return_baseline':z['always_no_return_accuracy'],'recall':z['pooled_recall'],'precision':z['pooled_precision'],'F1':z['pooled_f1'],'Brier':z['mean_brier']}]).round(4))")
    md('## Proposed predictors: building age and pest history\n**Building age is a proposed predictor, not an existing measured variable.** Collect year built or a defensible age band, the source, verification date and confidence. Calculate age at the service date, not today. Do not infer age from address, district, appearance or an AI answer. Unknown age must remain missing.\n\n**Building pest history needs a verified building identifier and time-stamped records.** Current property history is an existing proxy: prior recorded return counts, prior services, smoothed return rates and recency. Nearby-area counts provide local context but are also influenced by how many services Nomobug delivered. A building with more clients or visits can have more recorded returns without higher underlying pest risk. External technician/client history can be added only when dated, attributable and known before prediction. A current recollection without an event date is not a safe historical predictor.\n\nRecommended fields: `building_id`, `year_built_or_age_band`, `age_source`, `verified_at`, `prior_pest_report_date`, `pest_type`, `severity_scale_definition`, `history_source`, `report_known_at`. Distinguish no recorded history from verified no infestation. These fields are not yet available and cannot be tested honestly by inventing values.')
    md('## Next steps for supervisor discussion\n1. Agree on the target: recorded return after every paid service, or residential 3x return within 30 days after the actual third service. The latter matches the stated warranty window more directly.\n2. Audit a sample of positive and negative labels against source records, including cancellations, reschedules, linked upsells and missed/unrecorded return visits. Report disagreement rates; do not claim these labels are technician-verified yet. The blank `data/label_audit_template.csv` is for this future review, not evidence it has happened.\n3. Confirm which proposed building fields can actually be collected; see `data/proposed_building_predictors.csv`. Keep existing property-history predictors distinct from building-wide pest history.\n4. Use earlier data for predictor exploration and feature ablations. Compare service-only, history, weather and environmental blocks on the same eligible rows and temporal/group partitions. Do not choose a target or split just because it produces a larger accuracy.\n5. Freeze any new candidate before an independent future evaluation. Keep the existing frozen experiment and its receipts intact.\n\n## Source and method references\nProject sources and hashes are in `data/review_metadata.json`; aggregate hashes are in `data/manifest.json`. Relevant code: `scripts/benchmark_warranty_models.py`, `scripts/compare_callback_candidates_v2.py`, `scripts/evaluate_callback_holdout.py`, `scripts/freeze_corrected_callback.py`.\n\n[scikit-learn: data leakage and preprocessing](https://scikit-learn.org/stable/common_pitfalls.html) · [scikit-learn: cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html) · [SciPy: Spearman correlation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html)')
    nb=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':sys.version.split()[0]},'execution_method':'All code cells executed sequentially by local Python harness; no Jupyter kernel available.'})
    execute(nb)
    nbformat.validate(nb);nbformat.write(nb,OUT/'CP2_Model_Review.ipynb')
    export_html(nb,OUT/'CP2_Model_Review.html')
    (OUT/'README.txt').write_text('Open CP2_Model_Review.html to read without installing anything.\nOpen CP2_Model_Review.ipynb in Jupyter or VS Code to inspect/edit code. Run from this folder.\nRequirements for rerunning: Python, pandas, numpy, matplotlib.\nThis is an aggregate-only review; private labelled source rows are NOT included.\nThe private source generator is scripts/build_supervisor_model_review.py in the project.\nThe notebook uses saved aggregate inputs, not live sources or a new model fit.\nAll code cells executed in Python and notebook structure validated. No Jupyter kernel was available in the authoring environment.\n',encoding='utf-8')
    with zipfile.ZipFile(OUT/'CP2_Supervisor_Review.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in [OUT/'CP2_Model_Review.ipynb',OUT/'CP2_Model_Review.html',OUT/'README.txt',*sorted((OUT/'data').glob('*'))]:archive.write(path,path.relative_to(OUT))
    print(json.dumps({'folder':str(OUT),'cells':len(cells),'code_cells':sum(c.cell_type=='code' for c in cells),'top_associations':numeric.assign(strength=numeric.spearman_rho.abs()).sort_values('strength',ascending=False).head(5)[['feature','spearman_rho','available_rows']].to_dict('records')},indent=2))

def execute(nb):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    env={'__name__':'__main__'};counter=0
    for cell in nb.cells:
        if cell.cell_type!='code':continue
        counter+=1;cell.execution_count=counter;outputs=[]
        def display(value):
            data={'text/plain':str(value)}
            if hasattr(value,'to_html'):data['text/html']=value.to_html(index=False,border=0,escape=True)
            outputs.append(nbformat.v4.new_output('display_data',data=data))
        def show():
            for index in plt.get_fignums():
                fig=plt.figure(index);stream=io.BytesIO();fig.savefig(stream,format='png',bbox_inches='tight');outputs.append(nbformat.v4.new_output('display_data',data={'image/png':base64.b64encode(stream.getvalue()).decode()}));plt.close(fig)
        env['display']=display;plt.show=show
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):exec(compile(cell.source,'notebook-cell-'+str(counter),'exec'),env)
        if stream.getvalue():outputs.append(nbformat.v4.new_output('stream',name='stdout',text=stream.getvalue()))
        cell.outputs=outputs

def markdown(text):
    def inline(value):
        value=html.escape(value)
        value=re.sub(r'`([^`]+)`',r'<code>\1</code>',value)
        value=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',value)
        value=re.sub(r'\[([^]]+)\]\((https://[^)]+)\)',r'<a href="\2">\1</a>',value)
        return value
    parts=[]
    for block in text.split('\n\n'):
        if block.startswith('#'):
            line,*rest=block.splitlines();level=len(line)-len(line.lstrip('#'));parts.append(f'<h{level}>{inline(line.lstrip("# "))}</h{level}>')
            if rest:parts.append('<p>'+inline(' '.join(rest))+'</p>')
        else:parts.append('<p>'+inline(block).replace('\n','<br>')+'</p>')
    return '\n'.join(parts)

def export_html(nb,path):
    parts=['<!doctype html><html><meta charset="utf-8"><title>CP2 model review</title><style>body{max-width:1120px;margin:45px auto;padding:0 28px;font:16px/1.7 Arial;color:#1e293b;background:#f8fafc}h1{font-size:34px;color:#0f172a}h2{margin-top:52px;padding-top:22px;border-top:3px solid #2563eb;color:#172554}h3{margin-top:28px}section{background:white;padding:16px 24px;margin:15px 0;border:1px solid #e2e8f0;border-radius:10px}table{border-collapse:collapse;font-size:12px;display:block;overflow:auto}td,th{padding:9px;border-bottom:1px solid #e2e8f0;text-align:left}th{background:#eff6ff}img{max-width:100%;height:auto}pre{font:12px/1.6 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;padding:14px;background:#f1f5f9}details{margin:14px 0}summary{cursor:pointer;color:#2563eb}code{font-size:.88em}a{color:#1d4ed8}</style><body>']
    for cell in nb.cells:
        parts.append('<section>')
        if cell.cell_type=='markdown':parts.append(markdown(cell.source))
        else:
            parts.append('<details><summary>Show Python code</summary><pre>'+html.escape(cell.source)+'</pre></details>')
            for output in cell.outputs:
                data=output.get('data',{})
                if 'image/png' in data:parts.append('<img alt="Source-backed model analysis figure" src="data:image/png;base64,'+data['image/png']+'">')
                elif 'text/html' in data:parts.append(data['text/html'])
                elif output.output_type=='stream':parts.append('<pre>'+html.escape(output.text)+'</pre>')
                elif 'text/plain' in data:parts.append('<pre>'+html.escape(data['text/plain'])+'</pre>')
        parts.append('</section>')
    path.write_text('\n'.join(parts)+ '</body></html>',encoding='utf-8')

if __name__=='__main__':main()
