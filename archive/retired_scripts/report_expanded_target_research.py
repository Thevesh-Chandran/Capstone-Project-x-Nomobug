"""Portable plain-language notebook of the expanded, exploratory comparison."""
import json
from pathlib import Path
import nbformat
import pandas as pd
from scripts.research_expanded_targets import OUT,ROOT,save,sha
from scripts.build_supervisor_model_review import execute,export_html

def main():
    repeat=json.loads((OUT/'repeat_results.json').read_text());history=json.loads((OUT/'customer_history/results.json').read_text());forecasts=json.loads((OUT/'forecast_results.json').read_text())
    population=json.loads((OUT/'population_test/results.json').read_text());predictions=pd.read_csv(OUT/'forecast_assessment.csv')
    rows=[]
    for r in repeat:
        m=r['assessment'];rows.append({'Question':f"First purchase → another within {r['target'].split('_')[1]} days",'Test rows':m['n'],'Actual repeats':m['positives'],
            'Correct alerts':m['tp'],'False alerts':m['fp'],'Missed repeats':m['fn'],'Accuracy %':round(100*m['accuracy'],1),'Precision %':round(100*m['precision'],1),'Recall %':round(100*m['recall'],1),'Always-no accuracy %':round(100*(1-m['prevalence']),1)})
    for r in history:
        if r['policy']!='precision':continue
        m=r['assessment'];rows.append({'Question':f"Any programme purchase → another within {r['horizon']} days",'Test rows':m['n'],'Actual repeats':m['positives'],
            'Correct alerts':m['tp'],'False alerts':m['fp'],'Missed repeats':m['fn'],'Accuracy %':round(100*m['accuracy'],1),'Precision %':round(100*m['precision'],1),'Recall %':round(100*m['recall'],1),'Always-no accuracy %':round(100*(1-m['prevalence']),1)})
    names={'weekly_bookings':'Bookings next week','weekly_packages':'Packages sold next week','weekly_sales_rm':'Recorded sales next week (RM)'}
    frows=[]
    for r in forecasts:
        frows.append({'Question':names[r['target']],'Test weeks':r['assessment']['weeks'],'Selected model':r['selected']['model'],
            'Model average error':round(r['assessment']['mae'],2),'Simple baseline':r['baseline_selection']['model'],'Baseline average error':round(r['baseline_assessment']['mae'],2),
            'Model improvement %':round(100*r['mae_improvement'],1)})
    payload={'repeat':rows,'forecasts':frows,'forecast_points':predictions.to_dict('records'),'population':population,'history_results':history,
        'protected':json.loads((OUT/'completion.json').read_text()),'source_release':'cp2r_20261014045314a561c6'}
    cells=[]
    md=lambda text:cells.append(nbformat.v4.new_markdown_cell(text))
    code=lambda text:cells.append(nbformat.v4.new_code_cell(text,metadata={'tags':['hide-input']}))
    md('''# Finding a useful prediction model for Nomobug
**18 October 2026 — extended research, with real company records.**

## 1. The answer
**This search did not establish a model with both high accuracy and high precision.** No new model qualified for replacement or deployment.

The best practical direction remains simple weekly planning forecasts, with their expected error shown. For repeat purchases, adding past customer purchases helps, but the false-alert rate is still too high to call the result dependable.

This is a completed bounded comparison, not a claim that every possible algorithm or dataset has been exhausted. The existing frozen pest-return model and its future test remain unchanged.''')
    code('import json\nimport pandas as pd\nimport matplotlib.pyplot as plt\ndata=json.loads('+repr(json.dumps(payload,allow_nan=False))+')\nplt.rcParams.update({"font.size":11,"axes.spines.top":False,"axes.spines.right":False})\n')
    md('''## 2. What did we actually try?
**252 target/model/input/history configurations:** 96 first-purchase classifiers, 108 classifiers using each programme purchase, and 48 forecasting configurations. Threshold comparisons are additional decisions, not additional independent test samples. A further 10 paired fits tested district population.

Six classifier families: ordinary logistic regression, class-balanced logistic regression, random forest, extra trees, histogram gradient boosting and CatBoost. Forecasting compared ridge regression, extra trees, boosting and four simple baselines.

Each target answers a different question. A 180-day repeat purchase is not a 30-day pest return. A count forecast has an error in bookings or RM; it does not have classification precision.

The precision-focused and F1-focused rules selected the same candidate for each customer-history horizon. These are the same predictions, not two independent successes.''')
    md('''## 3. The new yes/no results
**Accuracy:** how often the overall yes/no answer was right.

**Precision:** when the model said “will buy again,” how often that happened.

**Recall:** how many actual repeat purchases it found.

All assessment purchase dates are 1 January–14 April 2026. Every 180-day window has matured by 11 October. The first-purchase study has 320 customers. The programme-level study has 356 purchase dates, with some customers repeated; it tests ongoing customer management.''')
    code("table=pd.DataFrame(data['repeat'])\ndisplay(table[['Question','Test rows','Actual repeats','Accuracy %','Precision %','Recall %','Always-no accuracy %']])")
    code("""subset=table.iloc[4:]
fig,ax=plt.subplots(figsize=(9,4))
x=list(range(len(subset)))
ax.bar([v-.18 for v in x],subset['Precision %'],.36,label='Precision',color='#2563eb')
ax.bar([v+.18 for v in x],subset['Recall %'],.36,label='Recall',color='#f59e0b')
ax.set_xticks(x,['30 days','90 days','180 days']);ax.set_ylim(0,105);ax.set_ylabel('Percent')
ax.set_title('Repeat purchase after any programme purchase',loc='left');ax.legend();plt.tight_layout();plt.show()
""")
    md('''The 90-day customer-history model made 34 “yes” predictions. **8 were right and 26 were wrong.** It found 8 of 15 repeat purchases and missed 7. Accuracy was 90.7%, but always saying “no” would score 95.8%.

Its 19 inputs include purchase details, past purchase counts/timing and regional weather. The model was chosen on earlier validation data, not because this assessment looked best. The sample has only 15 positive outcomes, so precision remains uncertain.''')
    code("""r=next(x for x in data['history_results'] if x['horizon']==90 and x['policy']=='precision')
display(pd.DataFrame([{'Model':r['selected']['model'],'Training rows':r['training_rows'],'Inputs':r['input_count'],
    'Precision 95% interval':f"{r['precision_95pct_cluster_interval'][0]*100:.1f}%–{r['precision_95pct_cluster_interval'][1]*100:.1f}%",
    'Recall 95% interval':f"{r['recall_95pct_cluster_interval'][0]*100:.1f}%–{r['recall_95pct_cluster_interval'][1]*100:.1f}%"}]))
""")
    md('''## 4. Could forecasting be stronger?
The models forecast one week ahead using past activity. The later assessment covers 14 weeks, 6 July–5 October 2026. Each week is predicted before its outcome enters the training history.

**Average error (MAE)** means how far the prediction was from the actual count or RM amount, on average. Lower is better. Baselines were selected using earlier validation, not picked from the assessment results.''')
    code("display(pd.DataFrame(data['forecasts']))")
    code("""p=pd.DataFrame(data['forecast_points']);p['date']=pd.to_datetime(p['date'])
fig,axes=plt.subplots(3,1,figsize=(10,9),constrained_layout=True)
names={'weekly_bookings':'Bookings','weekly_packages':'Packages sold','weekly_sales_rm':'Recorded sales (RM)'}
for ax,(target,part) in zip(axes,p.groupby('target',sort=False)):
    ax.plot(part.date,part.actual,'o-',color='#0f172a',label='Recorded')
    ax.plot(part.date,part.prediction,color='#2563eb',label='Selected model')
    ax.plot(part.date,part.baseline,'--',color='#e67e22',label='Simple baseline')
    ax.set_title(names[target],loc='left');ax.set_ylabel(names[target]);ax.legend(loc='upper right',fontsize=9)
plt.show()
""")
    md('''All three selected complex models lost to their simple baselines in the later period. The booking baseline missed by about **10.3 bookings per week**, compared with **10.9** for the weather-enhanced model. This is a realistic planning uncertainty, not “85% accuracy.”

The sample is only 14 weeks. Two-week block bootstrap intervals allow short-range dependence, but do not remove all selection bias or prove performance in future months.''')
    md('''## 5. Which inputs and outside datasets were used?
Purchase details: first-day amount and missingness, package, pest, premises, district, number of sale rows and seasonal month.

Customer history: earlier distinct programmes, days since first and last purchase, average earlier sale amount, and purchase counts in the preceding 90/365 days. Later upsell amounts never become earlier predictors.

Weather: 7-day and 28-day rain totals, 28-day average temperature and humidity. These periods end before the seven days immediately preceding prediction. Downloaded ERA5 data use a public Kuala Lumpur coordinate as a regional proxy, not the exact weather at each property. Revised reanalysis is not an original as-issued archive.

**District population:** downloaded DOSM's official dataset; 695 of 2,501 sale rows could join to a district. We tested 2020 district population and an unknown flag. It did not consistently improve both ranking and probability error, so it was not retained.

**Settlement age:** found Copernicus GHS-AGE, a 2025 release estimating dominant built-stock age in grid cells. It is a neighbourhood proxy, not a verified age of the customer's building. It was not trained here: the release did not exist for the early development periods, and precise point matches would require a separate spatial/vintage study.

**Public holidays:** official Malaysian calendars were found, but dates and announcement/revision timing were not extracted and tested in this round. **Online pest reports and individual building ages:** still no verified, dated property-level label source obtained.

These statuses distinguish data actually trained from sources merely found. Unrelated public training datasets cannot establish accuracy on Nomobug customers.''')
    code("display(pd.DataFrame(data['population']['decisions']).rename(columns={'horizon':'Days','folds':'Periods','folds_both_improved':'Periods improved on both measures','retain':'Keep population'}))")
    md('''## 6. How were the partitions kept fair?
First-purchase and programme studies used three chronological development periods: October–December 2024, January–March 2025, and April–June 2025. Every training outcome window ends before the next prediction period. The 180-day target had insufficient mature training history in the first period, so it uses the two 2025 periods; this feasibility amendment was recorded before its assessment.

Training-history choices were all earlier history versus the latest 365 days for customers, and all history versus 52 weeks for forecasting. These are tested alternatives, not arbitrary random splits selected for the largest score.

For customer models, family, inputs, history and threshold were chosen on development data before scoring the later period. For forecasts, development origins were every second week in January–June 2026, followed by weekly July–October assessment.

**Important limitation:** these historical records and periods were already inspected in earlier project research. This is an exploratory extension, not a pristine independent final test. The later customer-history extension was declared after reviewing the initial first-purchase results. More searching increases the chance of an optimistic finding.

Customer-history models may use the same customer's earlier purchases. That is valid for an ongoing customer tool, but is not a test exclusively on previously unseen customers. Its uncertainty intervals resample entire customer groups.

The company source is the pinned 14 October reporting release; this study did not refresh live Sheets or alter them. Missing dates, identity-review customers and immature outcomes are excluded; reconstructed source history and location missingness remain limitations.''')
    md('''## 7. What about the existing pest-return candidates?
Earlier research already tested 7/14/30/60-day windows, service-stage targets, residential populations, weather intervals, water/drain proximity, dated food-outlet maps, Calendar notes and variable removal/stepwise selection.

The previously highlighted **60-day after-final-service** candidate had **92.0% recall**, **38.1% precision**, and **53.4% accuracy** across 1,097 service windows. **92% was not its accuracy.** It used a different outcome and was selected from inspected historical results, so it is not a proven replacement.

The larger 30-day pest-return assessment had 2,075 services, 23.0% precision and 64.7% recall. The original 100-service result had only five positives. These are different fits and assessment designs; do not combine their scores or claim the frozen refit's future performance is already known.

The existing prospective model and collection receipts remain unchanged. Future results still require complete outcome extraction and collection checks.''')
    md('''## 8. Recommendation
**Use weekly planning estimates with explicit error ranges as the practical prediction feature. Keep purchase/return classifiers experimental.**

The customer-history model is a defensible research finding, but 26 false alerts out of 34 is not a high-precision system. Do not replace the original model just to show a larger-looking percentage.

No newly tested model passed the predeclared practical improvement gates. The next decisive evidence is a future evaluation of a fixed choice, not another percentage split chosen after reading its score.

## Sources and reproducibility
[Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api), [DOSM district population](https://data.gov.my/data-catalogue/population_district), [Copernicus GHS-AGE documentation](https://human-settlement.emergency.copernicus.eu/documents/GHS_AGE_R2025A.pdf), [official Malaysian holiday calendars](https://www.kabinet.gov.my/hari-kelepasan-am/), and [scikit-learn on model-selection bias](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html).

This notebook embeds aggregate results, so its tables and charts can run without customer data. Reproducing model fits requires the private project data and the research scripts. Protocols, hashes, validation searches, prediction receipts and downloaded datasets are stored beside it. Do not share the entire folder: it contains private customer exports.

Notebook cells were executed sequentially with the project's execution harness and validated as nbformat. A separate native Jupyter-kernel run was not performed.''')
    nb=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'}})
    execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Model_Research_Explained.ipynb');export_html(nb,OUT/'Model_Research_Explained.html')
    pd.DataFrame(rows).to_csv(OUT/'plain_classification_results.csv',index=False);pd.DataFrame(frows).to_csv(OUT/'plain_forecast_results.csv',index=False)
    save(OUT/'report_receipt.json',{'notebook_sha256':sha(OUT/'Model_Research_Explained.ipynb'),'executed_code_cells':sum(c.cell_type=='code' for c in nb.cells),'errors':sum(o.output_type=='error' for c in nb.cells if c.cell_type=='code' for o in c.outputs),'configuration_count':252,'paired_population_fits':10})

if __name__=='__main__':main()
