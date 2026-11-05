"""Readable, executed notebook for before-first-visit input screening."""
import json
import os
import nbformat
import pandas as pd
from scripts.test_before_first_weather import OUT
from scripts.build_supervisor_model_review import execute, export_html


def main():
    result=json.loads((OUT/'results.json').read_text())
    rows=result['summary']
    fold=pd.read_json(OUT/'fold_metrics.jsonl',lines=True)
    records=pd.DataFrame(rows)
    changes=[]
    for model,g in fold.groupby('model'):
        baseline=g[g.features.eq('baseline_existing_plus_between')].set_index('fold')
        for feature,part in g.groupby('features'):
            part=part.set_index('fold');delta=part.f1-baseline.f1
            changes.append({'model':model,'features':feature,'folds_f1_improved':int(delta.gt(0).sum()),
               'folds_ap_improved':int((part.average_precision-baseline.average_precision).gt(0).sum()),
               'folds_brier_improved':int((part.brier_score-baseline.brier_score).lt(0).sum()),
               'mean_fold_f1_change_points':float(delta.mean()*100)})
    pd.DataFrame(changes).to_csv(OUT/'input_consistency.csv',index=False)
    md=nbformat.v4.new_markdown_cell;code=nbformat.v4.new_code_cell
    nb=nbformat.v4.new_notebook(cells=[
      md('# Weather before the first visit\n\n**Finding: no consistent improvement.** For Extra Trees, adding seven-day rainfall alone raised F1 from 40.9% to 42.3%, but improved F1 in only two of four periods. Adding all 15 inputs gave 40.8%. Predicting a return for everyone gives 41.2% F1. These small differences do not justify replacing the model.\n\n**Question:** Does weather before the first visit improve prediction of a recorded pest-related return within 30 days after the third paid service?\n\nThis extends the previous test. Every comparison already includes weather between visits and before the third visit. No actual weather after the third service is used. The baseline is refitted in this experiment; compare variants within this run.'),
      md('## Did we add all 93 inputs one by one?\n\nNo. Earlier work removed each of the 93 inputs separately across three periods—279 refits—to see what happened without it. That is different from starting with one input and adding another until all 93 are included. A combined removal check did not consistently improve the model.\n\nHere we test **15 new inputs individually**: rainfall, heavy-rain days, average temperature, humidity and soil moisture, each measured over 7, 14 and 30 days before the first visit. Then we test all five together for each window and all 15 together. Rainfall per day is omitted because, for a fixed window, it duplicates total rainfall.\n\nTwo model types × 20 input sets × four chronological periods = 160 fits. These are input-variable tests, not a comprehensive search of every tree-depth or other model setting.'),
      code('import pandas as pd\nimport matplotlib.pyplot as plt\n'+f'records = {rows!r}\nconsistency = {changes!r}\n'+'''results=pd.DataFrame(records)
names={'baseline_existing_plus_between':'Existing + between visits','add_all_before_first_7d':'+ 7 days before first','add_all_before_first_14d':'+ 14 days before first','add_all_before_first_30d':'+ 30 days before first','add_all_before_first_windows':'+ All three windows'}
models={'et10_leaf5':'Extra Trees','lr_c1.0_plain':'Logistic regression'}
main=results[results.features.isin(names)].copy()
main['Model']=main.model.map(models);main['Inputs']=main.features.map(names)
for name in ['accuracy','recall','precision','f1']:
    main[name.title()+' %']=(100*main[name]).round(1)
display(main[['Model','Inputs','tested','returns','Accuracy %','Recall %','Precision %','F1 %']])
p=main.iloc[0]['returns']/main.iloc[0]['tested']
print(f'Always predict no return: accuracy {1-p:.1%}. Always predict return: F1 {2*p/(1+p):.1%}.')'''),
      code('''fig,ax=plt.subplots(figsize=(10,4.6))
for offset,(model,label) in enumerate(models.items()):
    g=results[results.model.eq(model)].set_index('features').reindex(names)
    ax.bar([i+offset*.36 for i in range(len(names))],100*g.f1,width=.34,label=label)
ax.axhline(100*main.iloc[0].always_yes_f1,color='#777777',linestyle='--',label='Always predict return')
ax.set_xticks([i+.18 for i in range(len(names))],list(names.values()),rotation=15,ha='right')
ax.set_ylabel('F1 (%) — balances detection and false alarms');ax.set_ylim(0,100)
ax.set_title('Does adding weather before the first visit help?')
ax.spines[['top','right']].set_visible(False)
ax.legend(loc='upper left',frameon=False,fontsize=9)
fig.tight_layout();fig.savefig('before_first_weather.png',dpi=160,bbox_inches='tight');plt.show()'''),
      md('## Which individual inputs helped?\n\nBelow are the individual additions with the largest average F1 improvement across periods, for each model. “Periods improved” shows repeatability. These are exploratory screening results from many comparisons, not proof that the top variable is reliable. Full results are in comparison.csv and input_consistency.csv beside this notebook.'),
      code('''checks=pd.DataFrame(consistency)
individual=checks[checks.features.str.startswith('add_before_first_')].copy()
def label(name):
    text=name.removeprefix('add_before_first_')
    for old,new in [('heavy_rain_days_10mm','heavy-rain days'),('rain_total_mm','total rainfall'),('temperature_mean_c','mean temperature'),('humidity_mean_pct','mean humidity'),('soil_moisture_mean','mean soil moisture')]:
        text=text.replace(old,new)
    return text.replace('_',' ')
individual['Input']=individual.features.map(label)
individual['Model']=individual.model.map(models)
individual['F1 change (points)']=individual.mean_fold_f1_change_points.round(1)
individual['Periods improved (of 4)']=individual.folds_f1_improved
best=individual.sort_values('mean_fold_f1_change_points',ascending=False).groupby('model').head(3)
display(best[['Model','Input','F1 change (points)','Periods improved (of 4)']])'''),
      md('## How to interpret this\n\nAdding more inputs does not automatically improve a model. One-at-a-time addition tests whether an input helps the current baseline; one-at-a-time removal tests whether it is needed when other inputs are present. Neither tests every possible interaction among 93 variables. Choosing whichever combination scores highest on these same records can overstate performance.\n\nAll variants use the same complete-weather rows. Training, calibration and validation are chronological and purge shared properties/sales. Thresholds are chosen from earlier calibration data only. The historical records were already explored, so the results are development evidence, not an independent final test. The frozen future model remains unchanged.\n\nWeather is coarse-grid historical reanalysis, not a replay of observations available in real time. The target is a recorded return, not independently verified pest recurrence or a formal warranty claim. Building age, flood and river-level observations are not included in this experiment.\n\nNotebook cells were executed sequentially in Python and validated with nbformat. A native Jupyter kernel was not available for an additional execution check.')])
    previous=os.getcwd()
    try:os.chdir(OUT);execute(nb)
    finally:os.chdir(previous)
    for cell in nb.cells:
        if cell.cell_type=='code':cell.metadata['jupyter']={'source_hidden':True}
    nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
    nbformat.validate(nb);nbformat.write(nb,OUT/'Weather_Before_First_Visit.ipynb')
    export_html(nb,OUT/'Weather_Before_First_Visit.html')
    print(records[records.features.eq('baseline_existing_plus_between')|records.features.str.startswith('add_all_')][['model','features','tested','returns','accuracy','recall','precision','f1']].to_string(index=False))

if __name__=='__main__':main()
