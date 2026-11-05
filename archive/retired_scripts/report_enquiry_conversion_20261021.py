"""Portable aggregate-only notebook for the enquiry feasibility experiment."""
from pathlib import Path
import json
import nbformat
from scripts.build_supervisor_model_review import execute, export_html
from scripts.research_enquiry_conversion_20261021 import OUT

def main():
    results=json.loads((OUT/'results.json').read_text())
    audit=json.loads((OUT/'dataset_audit.json').read_text())
    source=json.loads((OUT/'source_receipt.json').read_text())
    partitions=json.loads((OUT/'partition_audit.json').read_text())
    payload={'results':results,'audit':audit,'partitions':partitions,'release':source['release'],
      'queries':[{k:q[k] for k in ['job_id','row_count','bytes_processed','dry_run_bytes']} for q in source['queries']]}
    cells=[]
    def md(s):cells.append(nbformat.v4.new_markdown_cell(s))
    def code(s):cells.append(nbformat.v4.new_code_cell(s))
    md('''# Can enquiry details predict a later recorded sale?
**21 October 2026 — experimental historical test**

**Verdict: this test did not produce a useful high-precision model.** Only 30 of the 1,021 assessment contacts matched a sale in the defined future window. The selected models found one or two, with 16 or 23 false alerts. An always-no rule had higher overall accuracy.

The outcome is a **matching recorded sale**, not a verified won/lost enquiry or proof of settled payment.''')
    code('import json\nimport pandas as pd\nimport matplotlib.pyplot as plt\ndata=json.loads('+repr(json.dumps(payload,allow_nan=False))+')\nplt.rcParams.update({"font.size":11,"axes.spines.top":False,"axes.spines.right":False})')
    md('''## What the model sees

Seven inputs: acquisition channel; residential/business enquiry; pest enquiry; two month indicators; two weekday indicators. Month and weekday use a circular encoding so December/January and Sunday/Monday are adjacent.

It cannot see names, phone numbers, IDs, booking checkboxes, conversation status, WON remarks, objection categories, payment statuses, future followups, closing dates or sales amounts.

We compared ordinary logistic regression, balanced logistic regression, shallow Random Forest, shallow Extra Trees and histogram gradient boosting: **five fitted models and 80 validation threshold comparisons**. Thresholds do not create new independent samples.''')
    md('''## Source and partition

The enquiry and sale extracts come from one published immutable release. First dated staff reply per contact defines the origin. Strict phone matching excludes shared contacts, earlier customers and uncertain sale years. Same-day sales are excluded because source dates have no time of day.

Training outcomes mature before validation begins; validation outcomes mature before assessment begins. Contacts are unique and disjoint across all three partitions. The study was declared before assessment, but its historical months have been examined in the wider project.''')
    code("print('Published release:',data['release'])\nprint('Source observations through:',data['audit']['observed_through_local'])\ndisplay(pd.DataFrame(data['partitions']).T.rename(columns={'n':'Contacts','positives':'Matching sales'}))\nprint('Source query bytes:',sum(q['bytes_processed'] or 0 for q in data['queries']))")
    md('''## Results

The F1 policy balances precision and recall in validation. The precision policy required at least 30% validation recall and at least 20 validation alerts. Both were selected before opening assessment scores. Their later recall did not hold up.''')
    code("rows=[]\nfor r in data['results']['results']:\n    m=r['assessment'];rows.append({'Policy':r['policy'],'Model':r['selected']['model'],'Threshold':r['selected']['threshold'],'Test contacts':m['n'],'Matching sales':m['positives'],'Correct alerts':m['tp'],'False alerts':m['fp'],'Missed sales':m['fn'],'Accuracy %':100*m['accuracy'],'Precision %':100*m['precision'],'Recall %':100*m['recall']})\ntable=pd.DataFrame(rows)\ndisplay(table.round(2))\nprint('Always-no accuracy: {:.2f}%'.format(100*data['results']['baselines']['always_no']['accuracy']))")
    code("fig,axes=plt.subplots(1,2,figsize=(10,3.8))\nlabels=table.Policy.tolist()\naxes[0].bar(labels,table['Precision %'],color=['#2563eb','#7c3aed'])\naxes[1].bar(labels,table['Recall %'],color=['#2563eb','#7c3aed'])\nfor ax,title in zip(axes,['Correct alerts / all alerts','Found sales / all matching sales']):\n    ax.set_ylim(0,100);ax.set_ylabel('%');ax.set_title(title)\n    for p in ax.patches:ax.text(p.get_x()+p.get_width()/2,p.get_height()+2,f'{p.get_height():.1f}%',ha='center')\nfig.suptitle('Assessment: 1,021 contacts and 30 matching sales',fontsize=13)\nplt.tight_layout();plt.show()")
    md('''## What management can conclude

The initial fields provide weak evidence for predicting future matching sales. High raw accuracy mainly reflects that most contacts have no observed sale match. No classifier qualified for promotion, and the frozen pest-return model remains unchanged.

The phone link can miss changed numbers, shared household contacts and unrecorded sales. The source stores staff reply dates, not enquiry arrival timestamps. Source field availability is reconstructed from a later snapshot, so later edits to channel/pest/premise remain a limitation. These results cannot prove that an enquiry was lost, nor that a channel caused a sale.

Raw source exports and phone hashes remain private. This notebook contains aggregate results only. It can rerun the tables and plot without source access. Repeating the extraction and model fitting requires the authorised project environment and private files. The native Jupyter kernel was unavailable; cells were executed sequentially with the project's notebook executor.''')
    nb=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
    execute(nb);nbformat.validate(nb)
    target=OUT/'Enquiry_Conversion_Test.ipynb';nbformat.write(nb,target);export_html(nb,OUT/'Enquiry_Conversion_Test.html')

if __name__=='__main__':main()
