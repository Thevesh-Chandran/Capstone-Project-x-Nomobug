"""Concise supervisor notebook comparing forward and bidirectional selection."""
import json,os
import nbformat
from scripts import forward_select_return_predictors as forward
from scripts import stepwise_select_return_predictors as stepwise
from scripts import research_callback_targets as r
from scripts.simplify_supervisor_review import explain
from scripts.build_supervisor_model_review import execute,export_html

OUT=forward.b.ROOT/'outputs/model_validation/20261017_variable_selection'


def label(field):
    if field.startswith(('before_first_','first_to_second_','second_to_third_')):
        value=field.replace('before_first_','Before first visit: ').replace('first_to_second_','Visit 1 to 2: ').replace('second_to_third_','Visit 2 to 3: ')
        for old,new in [('rain_total_mm','total rainfall (mm)'),('rain_per_day_mm','rain per day (mm)'),('heavy_rain_days_10mm','heavy-rain days'),('temperature_mean_c','mean temperature (°C)'),('humidity_mean_pct','mean humidity (%)'),('soil_moisture_mean','mean soil moisture')]:value=value.replace(old,new)
        return value.replace('_',' ')
    return explain(field)[0]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    methods={'Forward selection':forward.OUT,'Stepwise selection':stepwise.OUT}
    paths=[];metrics=[];selected=[];receipts=[]
    for method,folder in methods.items():
        result=json.loads((folder/'results.json').read_text());protocol=json.loads((folder/'protocol.json').read_text())
        for item in result['path']:
            field=item.get('added',item.get('field'));operation=item.get('operation','add')
            paths.append({'Method':method,'Step':item.get('step',item.get('move')),'Change':operation+' '+label(field),'Inputs':len(item['columns']),'Earlier F1 (%)':100*item['mean_f1']})
        selected += [{'Method':method,'Input':label(x),'Technical field':x} for x in result['selected']]
        for variant,values in result['later_assessment'].items():
            total={k:sum(x[k] for x in values['folds']) for k in ['TP','FP','FN','TN']}
            tp,fp,fn,tn=[total[x] for x in ['TP','FP','FN','TN']];n=tp+fp+fn+tn
            metrics.append({'Method':method,'Version':variant,'Tested programmes':n,'Recorded returns':tp+fn,
               'Accuracy (%)':100*(tp+tn)/n,'Returns detected (%)':100*tp/(tp+fn),
               'Predicted returns correct (%)':100*tp/(tp+fp) if tp+fp else 0,'F1 (%)':100*2*tp/(2*tp+fp+fn),
               'False alarms':fp,'Missed returns':fn})
        receipts.append({'method':method,'protocol_sha256':r.digest(folder/'protocol.json'),'results_sha256':r.digest(folder/'results.json'),
          'stop_reason':result['stop_reason'],'selected':result['selected'],'frozen_unchanged':result['frozen_bundle_unchanged']})
    import pandas as pd
    pd.DataFrame(paths).to_csv(OUT/'selection_path.csv',index=False)
    pd.DataFrame(metrics).to_csv(OUT/'later_comparison.csv',index=False)
    pd.DataFrame(selected).to_csv(OUT/'selected_inputs.csv',index=False)
    r.write(OUT/'source_receipt.json',receipts)
    md=nbformat.v4.new_markdown_cell;code=nbformat.v4.new_code_cell
    nb=nbformat.v4.new_notebook(cells=[
      md('# Adding variables one by one\n\n**Result: both methods selected the same two inputs—pest type and a rodent indicator.** Later F1 was 39.6%, compared with 37.3% using all 101 inputs. However, predicting a return for everyone scored 40.6%. The smaller model did not establish useful improvement over that simple baseline, so nothing was deployed.\n\n**Question:** Which inputs help predict a recorded pest-related return within 30 days after a residential third paid service?\n\n**Forward selection** starts with the best single input, then tests every remaining input one at a time alongside the accepted inputs.\n\n**Stepwise selection** can add an input or remove an earlier input. Removing one can help when another input already captures the same information.'),
      md('## How we kept the comparison fair\n\nWe offered 122 inputs: the original 93 plus 29 timing and weather inputs. Twenty-one were constant in the earlier records, leaving 101 candidates. We selected inputs using July–December 2025 only. For each of those periods, fitting and calibration used earlier, mature records, with shared properties/sales purged.\n\nAn addition/removal needed at least 0.5 percentage points of average F1 improvement, without losing more than two points in either selection period. We stopped when no change passed that rule, with safety caps of 20 selected inputs and 30 stepwise moves. A small model is a valid result; adding all inputs is not required.\n\nAfter locking each selected set, we assessed it on January–14 August 2026. These later records were already examined in earlier project experiments, so this is a separated historical development comparison, not a new independent test. No live model was changed.'),
      code('import pandas as pd\nimport matplotlib.pyplot as plt\n'+f'path_records={paths!r}\nmetric_records={metrics!r}\nselected_records={selected!r}\n'+'''path=pd.DataFrame(path_records)
path['Earlier F1 (%)']=path['Earlier F1 (%)'].round(1)
display(path)
display(pd.DataFrame(selected_records)[['Method','Input']])'''),
      code('''fig,ax=plt.subplots(figsize=(9,4))
for method,g in path.groupby('Method',sort=False):
    ax.plot(g.Step,g['Earlier F1 (%)'],marker='o' if method=='Forward selection' else 's',linestyle='-' if method=='Forward selection' else '--',label=method)
ax.set_xlabel('Accepted selection step');ax.set_ylabel('Earlier validation F1 (%)')
ax.set_title('Did the next variable improve detection?');ax.set_ylim(0,100)
ax.set_xticks(sorted(path.Step.unique()));ax.spines[['top','right']].set_visible(False)
ax.legend(ax.lines,['Forward selection','Stepwise selection'],frameon=False,loc='upper left')
fig.tight_layout();fig.savefig('selection_path.png',dpi=160,bbox_inches='tight');plt.show()'''),
      md('## Performance on the later periods\n\nThe earlier two selection periods contain 440 programmes; the two later assessment periods contain 424 programmes, including 108 recorded returns. This split explains why the later result uses fewer than the previous 864 programme comparison.\n\n**Accuracy:** all predictions correct. **Returns detected:** actual returns caught. **Predicted returns correct:** how many alerts were right. **F1:** balances detection and false alarms.\n\nThe constant baseline uses the earlier training return rate and chooses its yes/no cutoff on earlier calibration records. In this assessment it predicts a return for everyone. Always predicting no return would give 74.5% accuracy but detect none of the 108 returns. The selected model’s accuracy was only 32.3%, so it is not a strong yes/no classifier.'),
      code('''metrics=pd.DataFrame(metric_records)
for col in metrics:
    if col.endswith('(%)'):metrics[col]=metrics[col].round(1)
metrics['Version']=metrics.Version.map({'constant_baseline':'Constant baseline','selected':'Selected inputs','all_inputs':'All 101 inputs'})
display(metrics)
fig,ax=plt.subplots(figsize=(9,4))
for i,(method,g) in enumerate(metrics.groupby('Method',sort=False)):
    ax.bar([x+i*.35 for x in range(3)],g['F1 (%)'],width=.33,label=method)
ax.set_xticks([x+.175 for x in range(3)],['Constant baseline','Selected inputs','All 101 inputs'])
ax.set_ylim(0,100);ax.set_ylabel('Later F1 (%)');ax.set_title('Later historical performance after selection was locked')
ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False);fig.tight_layout()
fig.savefig('later_assessment.png',dpi=160,bbox_inches='tight');plt.show()'''),
      md('## Limits\n\nThis searches one variable at a time. It can miss pairs that help only when introduced together, so it cannot guarantee the best combination among all possible subsets. Tree settings were fixed; these are input-variable searches, not a new hyperparameter search.\n\nOnly complete unique recorded stages 1–3, one consistent address and verified cached weather coverage were eligible. Weather excludes the third-service day and everything afterwards. Coarse historical reanalysis is not property-level or archived real-time weather.\n\nA recorded return is not an independently verified pest recurrence or formal claim. The frozen prospective bundle remains unchanged. Notebook cells were executed sequentially with Python and validated with nbformat; native Jupyter-kernel execution was not available.')])
    previous=os.getcwd()
    try:os.chdir(OUT);execute(nb)
    finally:os.chdir(previous)
    for cell in nb.cells:
        if cell.cell_type=='code':cell.metadata['jupyter']={'source_hidden':True}
    nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
    nbformat.validate(nb);nbformat.write(nb,OUT/'Variable_Selection.ipynb');export_html(nb,OUT/'Variable_Selection.html')
    print(pd.DataFrame(metrics).to_string(index=False))

if __name__=='__main__':main()
