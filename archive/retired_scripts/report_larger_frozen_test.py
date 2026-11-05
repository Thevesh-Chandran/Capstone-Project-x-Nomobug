"""Short, self-contained notebook for the agreed larger historical test."""
import json,os
import nbformat
from scripts.evaluate_larger_frozen_model import OUT
from scripts.build_supervisor_model_review import execute,export_html


def main():
    result=json.loads((OUT/'results.json').read_text());splits=json.loads((OUT/'split_audit.json').read_text())['parts']
    manifest=json.loads((OUT/'frozen_manifest.json').read_text())
    md=nbformat.v4.new_markdown_cell;code=nbformat.v4.new_code_cell
    nb=nbformat.v4.new_notebook(cells=[
      md('# Larger frozen-model test\n\n**Result:** the separate 93-input model was tested on **2,075 service windows**, with **184 recorded returns**. Precision was **23.0%**, recall **64.7%**, accuracy **77.7%** and F1 **34.0%**.\n\nIt caught 119 returns, missed 65 and raised 398 false alarms. This is stronger evidence than the original 100-service test, but the precision remains weak.\n\nThis is a newly fitted model with the original 93-input design. It is not an additional test of the exact existing frozen weights. The original frozen model and future collection remain unchanged.'),
      md('## Partition agreed before fitting\n\nTraining: 8 March 2024–31 May 2025. Validation: 1 July–30 November 2025. Test: 1 January–27 August 2026. June and December provide outcome gaps. Shared property/sale groups were removed from the earlier parts.\n\nThe training set fitted the classifier. Validation fitted probability calibration and chose the yes/no cutoff, which was **0.14**. The new classifier, calibrator and cutoff were saved and hashed before any test predictions were calculated. Test records were never used to refit this model or choose its cutoff.\n\nThe architecture stayed Extra Trees: 300 trees, maximum depth 10, minimum 5 records per leaf, balanced classes and seed 42. All 93 input variables were retained; the fitted decision rules differ because the training records differ.'),
      code('import pandas as pd\nimport matplotlib.pyplot as plt\nimport numpy as np\n'+f'splits={splits!r}\nresult={result!r}\n'+'''display(pd.DataFrame(splits).rename(columns={'part':'Part','services':'Services','return_windows':'Recorded returns','groups':'Property/sale groups'})[['Part','Services','Recorded returns','Property/sale groups']])
metrics=result['metrics']
comparison=[]
for name,row in [('New 93-input model',metrics),('Always predict no return',result['always_no']),('Always predict return',result['always_yes'])]:
    comparison.append({'Approach':name,**{label:round(row[key]*100,1) for key,label in [('accuracy','Accuracy %'),('recall','Returns detected %'),('precision','Predicted returns correct %'),('f1','F1 %')]}})
display(pd.DataFrame(comparison))'''),
      md('## What the predictions mean\n\nThe model predicted a return for 517 service windows. Only 119 of those recorded a return: **about 23 correct predictions per 100 alerts**. It caught approximately 65 of every 100 actual returns.\n\nAlways predicting no return gives 91.1% accuracy because returns are uncommon, but catches none. The model does better on F1 than either constant prediction strategy; its high false-alarm burden still limits usefulness.\n\nProbability ranking had ROC-AUC 0.786 and average precision 0.240, compared with a return frequency of 0.089. Brier probability error was 0.0735, versus 0.0809 for a constant probability using the training return rate. These indicate some predictive signal, not a dependable warranty decision.'),
      code('''matrix=np.array([[result['TN'],result['FP']],[result['FN'],result['TP']]])
fig,axes=plt.subplots(1,2,figsize=(11,4.5),gridspec_kw={'width_ratios':[1,1.15]})
ax=axes[0];ax.imshow(matrix,cmap='Blues',vmin=0,vmax=matrix.max())
labels=[['Correct no return','False alarm'],['Missed return','Correct return']]
for row in range(2):
    for col in range(2):
        ax.text(col,row,f'{matrix[row,col]:,}\\n{labels[row][col]}',ha='center',va='center',fontsize=11,color='white' if matrix[row,col]>.6*matrix.max() else '#172554')
ax.set_xticks([0,1],['No return','Return']);ax.set_yticks([0,1],['No return','Return'])
ax.set_xlabel('Predicted');ax.set_ylabel('Recorded outcome');ax.set_title('2,075 later service windows')
ax=axes[1];names=['Precision','Recall','Accuracy','F1'];keys=['precision','recall','accuracy','f1']
values=[100*metrics[k] for k in keys];ci=result['cluster_bootstrap_95']
errors=np.array([[values[i]-100*ci[k]['low'] for i,k in enumerate(keys)],[100*ci[k]['high']-values[i] for i,k in enumerate(keys)]])
ax.bar(names,values,color=['#2563eb','#14b8a6','#8b5cf6','#f59e0b'],yerr=errors,capsize=4)
for i,v in enumerate(values):ax.text(i,v+11,f'{v:.1f}%',ha='center',fontsize=10)
ax.set_ylim(0,105);ax.set_ylabel('%');ax.set_title('Performance with 95% group-bootstrap ranges')
ax.spines[['top','right']].set_visible(False);fig.tight_layout()
fig.savefig('larger_frozen_test.png',dpi=160,bbox_inches='tight');plt.show()
display(pd.DataFrame([{'Metric':k.title(),'Estimate %':round(100*metrics[k],1),'95% lower %':round(100*v['low'],1),'95% upper %':round(100*v['high'],1)} for k,v in ci.items()]))'''),
      md('## What we can conclude\n\nThe larger historical test did not demonstrate higher precision. It estimates precision around **19.3–26.9%** under a bootstrap that resamples property/sale groups. This range is conditional on this fitted model; it does not account for all previous model experiments or future changes.\n\nThe original 40% precision came from only two correct alerts out of five. Its population, training data and cutoff differ, so the old and new percentages are not a controlled comparison of sample size alone. A larger sample improves the evidence, not necessarily the score.\n\nThese records and modelling choices were explored previously. This evaluation keeps training, validation and test records separate within this run, but cannot be called a completely fresh independent test. The real future test remains separate.\n\nThe target is a recorded corrective Calendar return within 30 days. It is not a confirmed biological pest recurrence or a verified formal warranty claim. Repeated service windows can refer to the same corrective event. Historical source rules may differ from later owner clarifications.\n\n**Decision:** retain the original frozen future experiment unchanged. Keep this new model as a historical evaluation artifact; do not deploy it as an accurate warranty decision system.'),
      md('## Evidence and reproducibility\n\nThe folder contains protocol.json (agreed dates and rules), split_audit.json, frozen_manifest.json, the separate saved model, results.json and private per-service predictions. Customer identities and row-level predictions are excluded from this notebook.\n\nThe notebook contains embedded aggregate results and editable plotting code. Its cells were executed sequentially with Python and the file was validated with nbformat. A native Jupyter kernel was unavailable for an additional execution check.')])
    nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
    nb.metadata['cp2_evidence']={'model_sha256':manifest['model_sha256'],'protocol_sha256':manifest['protocol_sha256']}
    previous=os.getcwd()
    try:os.chdir(OUT);execute(nb)
    finally:os.chdir(previous)
    for cell in nb.cells:
        if cell.cell_type=='code':cell.metadata['jupyter']={'source_hidden':True}
    nbformat.validate(nb);nbformat.write(nb,OUT/'Larger_Frozen_Model_Test.ipynb')
    export_html(nb,OUT/'Larger_Frozen_Model_Test.html')
    print('Saved executed notebook and readable report')

if __name__=='__main__':main()
