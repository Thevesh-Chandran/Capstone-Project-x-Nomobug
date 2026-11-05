"""Small, portable supervisor notebook for the paired interval-weather experiment."""
import json
import nbformat
import pandas as pd
from scripts import test_interservice_weather as experiment
from scripts.build_supervisor_model_review import execute, export_html


def main():
    out=experiment.OUT
    result=json.loads((out/'results.json').read_text())
    coverage=json.loads((out/'coverage.json').read_text())
    folds=[{k:v for k,v in json.loads(x).items() if k in ['model','features','fold','f1']}
           for x in (out/'fold_metrics.jsonl').read_text().splitlines()]
    nb=nbformat.v4.new_notebook()
    md=nbformat.v4.new_markdown_cell;code=nbformat.v4.new_code_cell
    nb.cells=[md('# Does weather between services help?\n\n**Question:** After a residential customer’s third paid service, will a pest-related return be recorded within 30 days?\n\n**Finding: a small, mixed improvement—not a reliable model yet.** Extra Trees caught more returns when interval weather was added, but produced more false alarms. Its F1 rose from 37.3% to 41.2%; simply predicting a return for everyone also gives 41.2% F1 on this sample.\n\nWe tested 864 programmes across four periods, with 224 recorded returns. These are separate research fits, not the frozen model’s original 100-service test. Nothing was deployed.'),
      md('## What we compared\n\n1. Service details and previous pest history, including the number of days between visits.\n2. The same inputs plus the existing weather before the third visit.\n3. The same inputs plus weather between visits 1–2 and 2–3.\n4. Both sets of weather.\n\nFor each gap: total rain, rain per day, heavy-rain days (at least 10 mm), average temperature, humidity and soil moisture. The later service day is excluded because its full-day weather was not yet known. Flood and river-level data were not included: the available summaries do not establish complete daily observations for these intervals.'),
      code('import pandas as pd\nimport matplotlib.pyplot as plt\nfrom IPython.display import display\n'+f'coverage = {coverage!r}\n'+"display(pd.DataFrame([{'Complete programmes': coverage['complete_final_programmes'], 'With matching weather': coverage['matched_weather_programmes'], 'Recorded returns': coverage['positive_programmes']}]))"),
      md('## Results\n\nEvery model uses the same eligible records and the same chronological validation periods. Training excludes customers/properties present in its validation period and outcomes that were not yet complete. Calibration and the yes/no cutoff use earlier records only.\n\n**Accuracy:** all yes/no answers correct. **Recall:** returns detected. **Precision:** predicted returns that actually returned. **F1:** balances recall and precision. Always predicting “no return” is the accuracy baseline. A higher accuracy alone is not enough.'),
      code(f"records = {result['summary']!r}\n"+'''results = pd.DataFrame(records)
names = {'history_and_gap_lengths':'No weather','existing_pre_service_weather':'Existing weather','between_service_weather':'Between visits','both_weather_sets':'Both weather sets'}
model_names = {'et10_leaf5':'Extra Trees','lr_c1.0_plain':'Logistic regression','rf_depth6':'Random forest','hist_depth3':'Gradient boosting'}
table=results.copy()
table['Inputs']=table.features.map(names)
table['Model']=table.model.map(model_names)
for source,label in [('accuracy','Accuracy %'),('recall','Recall %'),('precision','Precision %'),('f1','F1 %'),('always_no_accuracy','Always no %')]:
    table[label]=(table[source]*100).round(1)
display(table[table.model.eq('et10_leaf5')][['Inputs','Accuracy %','Recall %','Precision %','F1 %','Always no %']])
print('Extra Trees shown because it is the frozen model’s model family; these are separate historical fits.')
p=results.iloc[0]['returns']/results.iloc[0]['tested']
print(f'Always predict return: accuracy {p:.1%}, recall 100%, precision {p:.1%}, F1 {2*p/(1+p):.1%}.')
print('Other model checks — F1 %, not independent model selection:')
display(table.pivot(index='Model',columns='Inputs',values='F1 %'))'''),
      code('''fig,axes=plt.subplots(1,2,figsize=(12,4.6))
for ax,metric,title in zip(axes,['f1','recall'],['Balanced detection (F1)','Returns detected (recall)']):
    for i,(contract,label) in enumerate(names.items()):
        part=results[results.features.eq(contract)].set_index('model').reindex(model_names)
        ax.bar([x+i*.19 for x in range(4)],part[metric]*100,width=.18,label=label)
    ax.set_xticks([x+.285 for x in range(4)],list(model_names.values()),rotation=20,ha='right')
    ax.set_ylim(0,100);ax.set_ylabel('%');ax.set_title(title);ax.spines[['top','right']].set_visible(False)
handles,labels=axes[1].get_legend_handles_labels()
fig.legend(handles,labels,fontsize=9,loc='upper center',bbox_to_anchor=(.5,.93),ncol=4,frameon=False)
fig.suptitle('Same records and time periods — four input sets',fontweight='bold')
fig.tight_layout(rect=[0,0,1,.86])
fig.savefig('interservice_weather_comparison.png',dpi=160,bbox_inches='tight')
plt.show()'''),
      md('## Did the improvement repeat?\n\nThe table below shows the F1 change in each period. Positive means the added interval weather helped; negative means it hurt. Compare both against no weather and against the existing weather inputs.'),
      code(f"fold_records = {folds!r}\n"+'''fold_data=pd.DataFrame(fold_records)
wide=fold_data.pivot(index=['model','fold'],columns='features',values='f1')
changes=pd.DataFrame({'Between visits vs no weather (points)':100*(wide.between_service_weather-wide.history_and_gap_lengths),'Both vs existing weather (points)':100*(wide.both_weather_sets-wide.existing_pre_service_weather)}).round(1)
display(changes.reset_index())'''),
      md('## Decision\n\nKeep interval weather as a research candidate, but do not replace the live model. Extra Trees and Random Forest improved F1 over their existing-weather versions in all four periods; Logistic Regression and Gradient Boosting did not. Extra Trees probability error and ranking did not improve in every period. Some cutoffs predicted a return for everyone in a period, showing that the decision rule remains unstable.\n\nThe highest pooled F1 among these explored fits was Random Forest with interval weather: 43.2%, compared with the always-return F1 of 41.2%. That small advantage does not establish dependable business value.\n\nThese are development results on previously explored historical data, not new independent accuracy. They test whether the extra inputs help prediction; they do not prove that weather causes pest returns. The target is a recorded pest-related return, not independently verified pest recurrence or a formal claim.\n\nWe excluded 18 programmes with multiple addresses and one whose weather could not reproduce the archived seven-day rainfall. Reanalysis describes a coarse weather grid; real-time weather availability was not independently replayed. Current geocodes were matched using archived address hashes. Building-level weather precision is not claimed.\n\nThe live frozen bundle was checked unchanged before and after fitting. Notebook cells were executed sequentially in Python and validated with nbformat; a native Jupyter kernel was not available for a second execution check.')]
    # Execute without requiring a separately installed IPython runtime.
    for cell in nb.cells:
        if cell.cell_type=='code':cell.source=cell.source.replace('from IPython.display import display\n','')
    import os
    previous=os.getcwd()
    try:
        os.chdir(out);execute(nb)
    finally:os.chdir(previous)
    nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
    for cell in nb.cells:
        if cell.cell_type=='code':cell.metadata['jupyter']={'source_hidden':True}
    nbformat.validate(nb)
    nbformat.write(nb,out/'Weather_Between_Services.ipynb')
    export_html(nb,out/'Weather_Between_Services.html')
    print('Saved executed notebook and HTML')

if __name__=='__main__':main()
