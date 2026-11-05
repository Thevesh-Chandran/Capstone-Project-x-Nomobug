"""Commercial-only price research after confirmation that home prices are fixed.

This is an adaptive follow-up after examining the broader price study. Historical
assessment is already inspected; no result is claimed as an independent test.
"""
from pathlib import Path
import json,re,hashlib
import pandas as pd
import numpy as np
from scripts import research_quote_estimate as quotes

OUT=quotes.ROOT/'outputs/model_validation/20261030_commercial_quote'

def sector(name):
    text=re.sub(r'\([^)]*\)',' ',str(name or '').upper())
    for label,pattern in [('food','RESTORAN|RESTAURANT|CAFE|COFFEE|KOPI|BAKERY|FOOD|AYAM|NASI|SEAFOOD|BURGER|KEK|KITCHEN|WARUNG'),
        ('school','SCHOOL|TADIKA|PASTI|TUISYEN|TASKA|UNIVERSITY|COLLEGE|SEKOLAH'),('health','CLINIC|KLINIK|DENTAL|HOSPITAL'),
        ('worship','MASJID|SURAU|CHURCH|TEMPLE'),('industrial','WAREHOUSE|FACTORY|KILANG|GUDANG'),
        ('hotel','HOTEL|HOMESTAY'),('retail','SHOP|RETAIL|PASARAYA|SUPERMARKET|DOBI|LAUNDRY')]:
        if re.search(pattern,text):return label
    return 'other_or_unknown'

def prepare():
    frame,_=quotes.prepare();source=json.loads((OUT/'source_private.json').read_text(encoding='utf-8'))
    lookup={r['sales_record_id']:r for r in source}
    frame=frame[(frame.premise=='COMMERCIAL')&frame.sessions.notna()&frame.sessions.gt(0)].copy()
    frame['business_type']=frame.sale_id.map(lambda sid:sector(lookup[sid]['customer_name_raw']))
    frame['time_trend_days']=(frame.date-pd.Timestamp('2024-01-01')).dt.days.astype(float)
    frame.to_csv(OUT/'labelled_commercial_quotes_private.csv',index=False)
    train,valid,test,split=quotes.partition(frame)
    info={'scope':'Commercial only; home pricing excluded by owner confirmation','rows':len(frame),'split':split,
      'samples':{name:{'rows':len(d),'customers':d.customer_group.nunique(),'from':str(d.date.min().date()),'to':str(d.date.max().date())} for name,d in [('training',train),('validation',valid),('assessment',test)]},
      'independence':'Adaptive historical research; broader assessment period already inspected; no pristine final test claim'}
    (OUT/'feasibility.json').write_text(json.dumps(info,indent=2),encoding='utf-8');return frame,info

def make_notebook():
    import shutil,nbformat
    from scripts.build_project_notebooks import notebook
    dest=quotes.ROOT/'notebooks/evidence/commercial_quote';dest.mkdir(parents=True,exist_ok=True)
    for name in ('results.json','feasibility.json','validation_results.json','input_effects.csv','protocol_before_training.json','source_receipt.json','coverage.json'):
        shutil.copy2(OUT/name,dest/name)
    # Keep unsuccessful targets visible instead of discarding their evidence.
    for folder,key in [('20261030_quote_estimate','all_prices'),('20261030_premise_classifier','premise_category')]:
        for name in ('results.json','feasibility.json'):
            shutil.copy2(quotes.ROOT/'outputs/model_validation'/folder/name,dest/(key+'_'+name))
    sections=[('md','''## Prediction question

Given the requirements of a commercial pest-control job, what package sales amount would be consistent with Nomobug's recorded jobs?

This is a numerical target in RM. Residential pricing is mostly fixed and is outside this commercial model. An estimate is a quotation benchmark, not an approved price, profit, or payment received.'''),
    ('code','''E = EVIDENCE / "commercial_quote"
result = json.loads((E/"results.json").read_text())
scope = json.loads((E/"feasibility.json").read_text())
validation = pd.read_json(E/"validation_results.json")
print("Selected model:",result["selected"])
print("Passed exploratory research criteria:",result["passed_research_gate"])
print("Deployed:",result["deployed"])
'''),
    ('md','''## Result

The selected gradient-boosting model learns log price per recorded session, then multiplies the estimate by the supplied number of sessions. On 82 later commercial sales, average absolute error was RM201.79 versus RM271.41 for a requirements-based price lookup: 25.7% lower error. Median percentage error was 6.1%; 80.5% of estimates were within 20% of the recorded price. R-squared was 0.792.

These are exploratory historical results. This commercial study followed an earlier price study that examined the same later months. It is not an untouched independent test. A future quote comparison is needed before relying on it operationally.'''),
    ('md','''## Labelled data and partition

The label is the recorded Sales amount, not a synthetic category. Free, unknown or unresolved amounts, missing dates and pooled programme members are excluded. This commercial study additionally needs a known positive session count.

The date-only split uses the 60th and 80th percentile sale dates, then purges customer groups across partitions. Model settings and target transformations were selected using validation MAE. The selected model was refitted on training plus validation before assessment.'''),
    ('code','''display(pd.DataFrame([{"Partition":name,**values} for name,values in scope["samples"].items()]))
print("Final fit rows:",result["final_fit_rows"])
coverage=json.loads((E/"coverage.json").read_text())
display(pd.DataFrame([{"Recorded commercial sales":coverage["commercial_rows"],
                      "Area measurements found":coverage["source_name_address_package"]["area_sqft"],
                      "Explicit lot/unit counts found":coverage["source_name_address_package"]["lot_count"]}]))
'''),
    ('md','''## Inputs

Current sale amounts, deposits, balances, invoices, full package names, customer names and IDs are not predictors. Explicit prices embedded in package text are removed before extracting service requirements. Total price divided by session count is the training target transformation; the current total price is never supplied as an input at prediction time.

Commercial premise type is a fixed scope field, not an extra fact staff need to predict. Business-type and time-trend additions were tested but were not selected.'''),
    ('code','''meaning={
 "sessions":("Recorded sessions","Numerical","Number of sessions requested for the package"),
 "tbs_units":("TBS units mentioned","Numerical","Explicit unit count in package text; zero means not stated"),
 "trbs_units":("TRBS units mentioned","Numerical","Explicit unit count in package text; zero means not stated"),
 "includes_car":("Car mentioned in package","Binary","Whether the package text mentions a car component"),
 "misting":("Misting mentioned","Binary","Whether misting appears in package requirements"),
 "fogging":("Fogging mentioned","Binary","Whether fogging appears in package requirements"),
 "service_family":("Service family","Categorical","GPC, TBS, TRBS or other, without the price-bearing package name"),
 "premise":("Commercial scope","Fixed category","All records in this model are commercial"),
 "pest":("Pest category","Categorical","Recorded pest category"),
 "district":("District","Categorical","Mapped district; uncertain districts remain unassigned")}
display(pd.DataFrame([{"Input":meaning[k][0],"Type":meaning[k][1],"Meaning":meaning[k][2]} for k in result["raw_inputs"]]))
'''),
    ('md','''## Model comparison

Nine regression configurations were compared using requirements alone or with business type/time, and four target representations: original RM, log RM, price per session and log price per session. This gives 72 validation fits. The lowest validation MAE selected the final configuration. These are different from the earlier all-customer price test.'''),
    ('code','''columns=["candidate","inputs","mae_rm","rmse_rm","r_squared","median_absolute_percentage_error"]
display(validation[columns].sort_values("mae_rm").head(15).round(3))
best=validation.sort_values("mae_rm").head(10).sort_values("mae_rm",ascending=False)
fig,ax=plt.subplots(figsize=(12,6))
ax.barh(best.candidate,best.mae_rm,color="#2563eb")
ax.set(xlabel="Validation MAE (RM) — lower is better",title="Commercial price models selected on 75 validation sales")
fig.tight_layout();plt.show()
'''),
    ('md','''## Train the selected model

The selected model is a gradient-boosting regressor with absolute-error loss, 200 iterations, 15 maximum leaf nodes, minimum leaf size 10 and L2 regularisation 10. The code below recreates its fit when the private labelled data are available. It does not repeat selection, rewrite the source data or deploy the result.'''),
    ('code','''from sklearn.compose import ColumnTransformer,TransformedTargetRegressor
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
import numpy as np,sys
project=BASE.parent
if str(project) not in sys.path:sys.path.insert(0,str(project))
private=project/"outputs/model_validation/20261030_commercial_quote/labelled_commercial_quotes_private.csv"
if private.exists():
    from scripts.research_quote_estimate import PerSessionRegressor,partition
    rows=pd.read_csv(private,parse_dates=["date"],float_precision="round_trip")
    training,tuning,assessment,_=partition(rows)
    features=result["raw_inputs"]
    cats=[c for c in features if not pd.api.types.is_numeric_dtype(rows[c])]
    nums=[c for c in features if c not in cats]
    prepare=ColumnTransformer([
      ("numbers",make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),StandardScaler()),nums),
      ("categories",OneHotEncoder(handle_unknown="ignore",min_frequency=5,sparse_output=False),cats)])
    regression=make_pipeline(prepare,HistGradientBoostingRegressor(loss="absolute_error",max_iter=200,max_leaf_nodes=15,min_samples_leaf=10,l2_regularization=10,random_state=20261030))
    model=PerSessionRegressor(TransformedTargetRegressor(regressor=regression,func=np.log1p,inverse_func=np.expm1))
    fit_rows=pd.concat([training,tuning],ignore_index=True)
    model.fit(fit_rows[features],fit_rows.target_rm)
    predicted=np.maximum(0,model.predict(assessment[features]))
    replay_error=mean_absolute_error(assessment.target_rm,predicted)
    assert abs(replay_error-result["test"]["mae_rm"])<1e-6
    print("Selected model refitted on",len(fit_rows),"sales. Assessment MAE reproduced:",round(replay_error,2),"RM")
else:
    print("Private rows are not included. Saved aggregate results remain readable; model refitting needs the private project data.")
'''),
    ('md','''## Assessment against the price lookup

The baseline uses training-only median prices for the same service requirements, with service-family fallback. It is a realistic competitor, not just a weak global mean. The uncertainty interval resamples customer groups rather than treating repeated sales as independent. Its interpretation is conditional on this exploratory historical study.'''),
    ('code','''a,b=result["test"],result["baseline"]
display(pd.DataFrame([{"Measure":"MAE (RM)","Model":a["mae_rm"],"Lookup":b["mae_rm"]},
 {"Measure":"MSE (RM squared)","Model":a["mse_rm_squared"],"Lookup":b["mse_rm_squared"]},
 {"Measure":"RMSE (RM)","Model":a["rmse_rm"],"Lookup":b["rmse_rm"]},
 {"Measure":"R-squared","Model":a["r_squared"],"Lookup":b["r_squared"]},
 {"Measure":"Median percentage error","Model":a["median_absolute_percentage_error"]*100,"Lookup":b["median_absolute_percentage_error"]*100},
 {"Measure":"Within 20% of recorded price (%)","Model":a["within_20_percent"]*100,"Lookup":b["within_20_percent"]*100}]).round(3))
print("95% customer-bootstrap interval for MAE improvement (RM):",[round(v,2) for v in result["bootstrap_MAE_improvement_rm_95"]])
fig,axes=plt.subplots(1,2,figsize=(10,4))
axes[0].bar(["Lookup","Model"],[b["mae_rm"],a["mae_rm"]],color=["#94a3b8","#2563eb"])
axes[0].set(ylabel="Average absolute error (RM)",title="25.7% lower average error")
axes[1].bar(["Lookup","Model"],[b["within_20_percent"]*100,a["within_20_percent"]*100],color=["#94a3b8","#2563eb"])
axes[1].set(ylabel="Estimates within 20% of recorded price (%)",ylim=(0,100),title="Tolerance coverage is not classification accuracy")
fig.tight_layout();plt.show()
'''),
    ('md','''## Input importance

The chart measures how much validation MAE rises when an input is shuffled. Session count also controls conversion from the per-session estimate to the total price. Importance describes this fitted model; it does not prove a causal effect or statistical significance.'''),
    ('code','''effects=pd.read_csv(E/"input_effects.csv")
effects["Input"]=effects.input.map(lambda k:meaning[k][0])
display(effects[["Input","validation_MAE_increase_rm","sd_rm"]].round(2))
view=effects.sort_values("validation_MAE_increase_rm")
fig,ax=plt.subplots(figsize=(10,5))
ax.barh(view.Input,view.validation_MAE_increase_rm,color=["#2563eb" if v>0 else "#94a3b8" for v in view.validation_MAE_increase_rm])
ax.axvline(0,color="#334155",linewidth=1)
ax.set(xlabel="Increase in validation MAE when shuffled (RM)",title="What the commercial quotation model uses")
fig.tight_layout();plt.show()
'''),
    ('md','''## Other targets tested

The earlier all-premise price model did not beat its lookup overall, and residential pricing is mostly fixed. A separate name/address classifier for residential versus commercial categories reached 79.9% accuracy, but its advantage over a keyword rule was uncertain and it failed its research criteria. Neither is promoted. Different target metrics are not interchangeable and should not be ranked by whichever percentage is largest.'''),
    ('code','''other=json.loads((E/"all_prices_results.json").read_text())
text=json.loads((E/"premise_category_results.json").read_text())
display(pd.DataFrame([
 {"Study":"All-premise price","Selected":other["selected"],"Result":"MAE RM %.2f vs lookup RM %.2f"%(other["test"]["mae_rm"],other["baseline"]["mae_rm"]),"Passed":other["passed_research_gate"]},
 {"Study":"Name/address premise category","Selected":text["selected"],"Result":"Accuracy %.1f%% vs keyword %.1f%%"%(text["test"]["accuracy"]*100,text["keyword_baseline"]["accuracy"]*100),"Passed":text["passed_research_gate"]},
 {"Study":"Commercial price","Selected":result["selected"],"Result":"MAE RM %.2f vs lookup RM %.2f"%(a["mae_rm"],b["mae_rm"]),"Passed":result["passed_research_gate"]}]))
'''),
    ('md','''## Business use and limits

The commercial model can provide a reference price after staff specify the service requirements. Staff can compare a proposed quotation with the estimate and investigate a large difference. It must not automatically set a final price.

Property floor area, infestation severity and actual treatment cost are not reliably recorded. No floor-area measurements were found in 418 commercial Sales records. A separate Calendar description check below recovers some measurements; they were not inputs to this initial model. Jobs with the same recorded requirements can therefore still need different prices. Large individual errors remain possible: RMSE is RM437 despite a much smaller median error.

The model passed exploratory research criteria, not a production acceptance test. There are only 82 assessment sales, the historical months were inspected before this focused study, and source edits cannot be fully reconstructed. Save future predictions before quoting and compare with a later recorded Sales amount before claiming reliable live performance.

No website feature, current production model or frozen prospective experiment was changed by this research. Source query/job IDs are in `evidence/commercial_quote/source_receipt.json`; full training is in `scripts/research_commercial_quote.py` and `scripts/research_quote_estimate.py`. Notebook cells execute sequentially in Python; no native Jupyter kernel is installed.''')]
    sizes=quotes.ROOT/'outputs/model_validation/20261030_calendar_quote_sizes'
    if (sizes/'results.json').exists():
        for name in ('coverage.json','results.json','protocol_before_training.json','source_receipt.json'):
            shutil.copy2(sizes/name,dest/('calendar_sizes_'+name))
        sections.extend([
          ('md',"""## Calendar floor area and floor counts
The owner confirmed that premises sizes are recorded in Calendar descriptions. Explicit measurements were extracted from the same pinned Calendar snapshot and linked using existing sale matches. Unitless dimensions, ambiguous sizes and address floor numbers are not assumed to be treatment area or floor count.

Of 407 commercial sales, 99 have a linked explicit area. Only 68 have a consistent area passing the sale-day timestamp screen: 50 training, 7 validation and 7 assessment, with four in the customer-purge gap. Only three sales have an eligible floor-count mention. Sale-day availability is still not proof that the details were available before quoting.

The same selected model and chronological customer-separated partitions were tested with area, and then area plus floors. Validation error was identical for all three variants, so the simpler original model remains selected. Assessment average error changed from RM201.79 to RM201.63, which does not establish a useful improvement. No model was deployed. Implementation: `scripts/research_calendar_quote_sizes.py`."""),
          ('code',"""sizes = EVIDENCE / 'commercial_quote'
size_coverage = json.loads((sizes / 'calendar_sizes_coverage.json').read_text())
size_results = json.loads((sizes / 'calendar_sizes_results.json').read_text())
display(pd.DataFrame(size_coverage['partitions']).T)
display(pd.DataFrame(size_results['assessment'])[['candidate','rows','mae_rm','rmse_rm','r_squared','within_20_percent']])
""")])
    refinement=quotes.ROOT/'outputs/model_validation/20261101_commercial_refinement'
    if (refinement/'results.json').exists():
        for name in ('coverage.json','results.json','protocol_before_training.json','selected_before_assessment.json'):
            shutil.copy2(refinement/name,dest/('refinement_'+name))
        sections.extend([
          ('md',"""## Existing-data refinement — 1 November 2026
Explicit-unit dimensions such as 19 ft × 70 ft and 2k sqft were recovered from labelled Calendar size fields. Unitless dimensions, mixed units and conflicting measurements remain unknown. This increases consistent sale-day area coverage from 68 to 72 of 407 sales; assessment coverage rises from 7 to 8 of 82. Three sales have an explicit eligible floor count, all in training.

Nine fixed configurations compare gradient boosting, Ridge regression and Extra Trees, with requirements alone, size plus missing-value indicators, and then business type. The same 213 training, 75 validation and 82 assessment sales are retained. Training-only imputation does not establish true floor area for unknown premises. This remains adaptive historical research; recorded size may not equal area treated, and sale-day timestamps do not prove pre-quotation availability.

The validation-selected Ridge candidate reduces assessment RMSE from RM437 to RM364 and increases R² from 0.792 to 0.856. However, average absolute error changes only from RM201.79 to RM200.70; the 95% customer-bootstrap improvement interval spans −RM42.77 to +RM43.81. Estimates within 20% fall from 80.5% to 68.3%, and median percentage error rises from 6.1% to 11.2%. This is a trade-off, not an established replacement. The original commercial candidate remains the reference; neither is approved for automatic pricing.

The training-only median price-per-session benchmark has MAE RM240.57. The commercial candidate therefore adds some historical value beyond session multiplication alone. Full experiment: `scripts/research_commercial_quote_refinement.py`."""),
          ('code',"""refinement = json.loads((E / 'refinement_results.json').read_text())
refinement_coverage = json.loads((E / 'refinement_coverage.json').read_text())
display(pd.DataFrame(refinement_coverage['partitions']).T)
comparison = pd.DataFrame(refinement['assessment'])
comparison['Label'] = ['Original commercial candidate', 'New validation-selected candidate', 'Median price per session']
display(comparison[['Label','rows','mae_rm','rmse_rm','r_squared','within_20_percent']].round(3))
"""),
          ('code',"""fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
colors = ['#2563eb', '#e69f00', '#94a3b8']
labels = ['Original', 'New candidate', 'Session lookup']
for ax, column, title, ylabel in [(axes[0], 'mae_rm', 'Average absolute error', 'RM — lower is better'), (axes[1], 'within_20_percent', 'Estimates within 20% of recorded price', 'Percent of 82 sales')]:
    values = comparison[column].to_numpy() * (100 if column == 'within_20_percent' else 1)
    ax.bar(labels, values, color=colors)
    ax.set_title(title); ax.set_ylabel(ylabel)
    ax.set_ylim(0, 100 if column == 'within_20_percent' else max(values)*1.22)
    for index, value in enumerate(values): ax.text(index, value + (2 if column == 'within_20_percent' else 4), f'{value:.1f}', ha='center')
fig.tight_layout(); plt.show()
""")])
    entry=notebook('10_Commercial_Quote_Model','Commercial Quotation Model',sections)
    path=quotes.ROOT/'notebooks'/entry['file'];nb=nbformat.read(path,as_version=4)
    nb.metadata['cp2']={'scope':'Exploratory commercial quotation regression; no deployment','built':'2026-10-30','native_jupyter_kernel':False}
    nbformat.write(nb,path);return entry

if __name__=='__main__':
    import sys
    frame,info=prepare();print(json.dumps(info,indent=2),flush=True)
    if '--train' in sys.argv:
        sets={'commercial_requirements':quotes.REQUIREMENTS,
              'business_type_and_time':quotes.REQUIREMENTS+['business_type','time_trend_days']}
        result=quotes.study(frame,output_dir=OUT,feature_sets=sets,include_per_session=True,
            research_context={'scope':info['scope'],'independence':info['independence'],
              'commercial_source_sha256':hashlib.sha256((OUT/'source_private.json').read_bytes()).hexdigest()})
        result['scope']='Commercial quotation benchmark only; residential prices are fixed'
        result['limitations'].append(info['independence'])
        (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
