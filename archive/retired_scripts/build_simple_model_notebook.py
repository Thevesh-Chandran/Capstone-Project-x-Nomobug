"""One portable, plain-language notebook; complete variable details collapsed."""
import base64,hashlib,json
from pathlib import Path
import pandas as pd
import nbformat
from scripts.build_supervisor_model_review import execute

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/supervisor_model_review/20261017/data'
OUT=ROOT/'outputs/supervisor_model_review/20261017'

def main():
    variables=pd.read_csv(SOURCE/'variables_plain_english.csv')
    removal=pd.read_csv(SOURCE/'individual_removal_decisions.csv')
    numeric=pd.read_csv(SOURCE/'numeric_associations.csv')
    full=variables.merge(removal.drop(columns='Variable'),on='Technical field',validate='one_to_one')
    assert len(full)==93
    payload={'variables':full.to_dict('records'),'correlations':numeric[['feature','spearman_rho']].fillna('Unavailable').to_dict('records'),
      'group_tests':pd.read_csv(SOURCE/'group_decisions.csv').to_dict('records'),
      'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE/'variables_plain_english.csv',SOURCE/'individual_removal_decisions.csv',SOURCE/'numeric_associations.csv',SOURCE/'group_decisions.csv']}}
    cells=[]
    def md(s):cells.append(nbformat.v4.new_markdown_cell(s))
    def code(s):cells.append(nbformat.v4.new_code_cell(s,metadata={'jupyter':{'source_hidden':True},'tags':['hide-input']}))
    md('''# CP2 model — simple explanation
**Read sections 1–5. The full variable list at the end is optional.**

## 1. What are we predicting?
**Will a pest-related return be recorded within 30 days after this paid service?**

The answer is **Yes (1)** or **No (0)**. A normal next package visit is not a pest-related return. A recorded return is not automatically a verified formal warranty claim.

The frozen model was fitted on **5,695 service records**. It uses **93 inputs**. We have **not yet shown that it is reliable enough for business decisions**.''')
    code('''import json
import pandas as pd
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':11, 'axes.spines.top':False, 'axes.spines.right':False})
saved_data=json.loads('''+repr(json.dumps(payload,allow_nan=False))+''')
variables=pd.DataFrame(saved_data['variables'])
assert len(variables)==93
'''.replace('from IPython.display import display\n',''))
    # Jupyter provides display; the execution harness supplies the same interface.
    md('''## 2. What information goes into it?
Think of the inputs as **six groups**, rather than 93 unrelated things. Some inputs repeat the same idea in different forms.''')
    code('''group_names={
 'Service, package and premises':('The service and package','Visit number, package size, price, client type','Numbers, categories, yes/no'),
 'Pest category and indicators':('Which pests are recorded','Cockroaches, ants, rodents; pest combinations','Categories and yes/no'),
 'Past recorded pest/service history':('What happened before','Earlier visits and returns at the property/package/area','Numbers and yes/no'),
 'Weather before service':('Recent weather','Rain, temperature, humidity, soil moisture','Numbers'),
 'Geographic environment':('Nearby environment','Distance to water or drains, water features, elevation','Numbers'),
 'Derived weather interactions':('Combinations of inputs','Rain combined with nearby water or service stage','Calculated numbers')}
overview=[]
for group,(name,examples,kind) in group_names.items():
    overview.append({'Information':name,'Examples':examples,'Input type':kind,'How many':int(variables.Group.eq(group).sum())})
display(pd.DataFrame(overview))
assert sum(row['How many'] for row in overview)==93
''')
    md('''## 3. Did we check whether the inputs help?
**Yes. We retrained without each input, one at a time, in three earlier periods: 279 tests. We also removed whole groups.**

Removing weather or pest information generally weakened the model’s ranking of returns. Other group results were mixed. **Four individual inputs looked removable**, but removing all four together did not consistently help. So there is **no proven better replacement yet**.

This chart shows a different question: **what is associated with more or fewer returns?** It uses 5,333 earlier records. It does not show causes or statistical significance.''')
    code('''correlations=pd.DataFrame(saved_data['correlations']).set_index('feature')
examples={
 'anchor_remaining_services':'Paid visits remaining',
 'service_number':'Service number',
 'anchor_service_progress':'Progress through package',
 'prior_property_warranty_claims':'Earlier recorded property returns',
 'prior_14d_precipitation_mm':'Rain in previous 14 days',
 'hotosm_nearest_drainage_m':'Distance to mapped drain'}
values=[float(correlations.loc[field,'spearman_rho']) for field in examples]
fig,ax=plt.subplots(figsize=(9,4))
ax.barh(list(examples.values()),values,color=['#2563eb' if x>=0 else '#d97706' for x in values])
ax.invert_yaxis();ax.axvline(0,color='#64748b',linewidth=1)
ax.set_xlim(-.28,.28);ax.set_xlabel('Correlation: negative = fewer returns; positive = more returns')
ax.set_title('Observed relationships — not proof that an input improves predictions',loc='left',fontsize=12,pad=16)
for i,value in enumerate(values):
    ax.text(value+(.008 if value>=0 else -.008),i,f'{value:+.3f}',ha='left' if value>=0 else 'right',va='center',fontsize=10)
plt.tight_layout();plt.show()
''')
    md('''**What to take from this:** service stage has a clearer relationship than these rain and drain examples. Even the stage correlations are modest. The three stage inputs overlap, so they are not three independent discoveries. Near-zero correlation does not rule out a nonlinear effect in a tree model.

**“Significant” is not established here.** The records include repeated properties; we have not used an ordinary p-value to claim an independent or causal effect.

## 4. How good is the model so far?
The earlier historical test contained **100 services, including 5 returns**. The model caught **2**, missed **3**, and incorrectly flagged **3** non-return cases.

Accuracy was **94%**. Always predicting “no return” would score **95%**. So high accuracy alone does not make this model useful. This historical test used an earlier fitted model; the later frozen refit needs its separate future test.

## 5. What have we added, and what is still missing?
- **Nearby food:** collected current map data for 1,127 cached locations; 781 have mapped food places within 500 m. One result is capped. **Not trained yet**: historical opening/closing dates and precise customer matches need checking.
- **Building age:** no verified ages obtained. A 100-location check found no date tags in returned records; 40 responses were capped. **Not trained.**
- **Treatment facilities:** official sources found, but coordinates, operating dates and coverage still need verification. **Not trained.**
- **Online building pest history:** no verified general source obtained. Company return history is already included; dengue data is not an all-pest history.

**Bottom line for the supervisor:** we tested the existing inputs, but no consistently better model is established. We need better verified inputs and labels, then a separate candidate evaluation. The frozen future test is unchanged.'''.replace('**Bottom line for the supervisor:**','**What I can tell my supervisor:**'))
    md('''## Optional: every input, in plain English
Expand the table below only when you need to check a specific variable. “Removal result” comes from historical development tests, not an independent final test. Four removal candidates are tentative; the other 89 have mixed evidence, which does not prove they are necessary.''')
    code('''table=variables[['Variable','What it means','Type','Observed relationship','Decision']].rename(columns={'Decision':'Removal result'})
class ExpandableTable:
    def to_html(self,**kwargs):
        return '<details><summary><b>Open the full 93-variable list</b></summary>'+table.to_html(index=False,border=0)+'</details>'
    def _repr_html_(self):
        return self.to_html()
    def __repr__(self):
        return 'Full 93-variable table: expand the HTML output in Jupyter.'
display(ExpandableTable())
''')
    md('''### Sources and rerunning
The aggregate inputs are embedded in this notebook; no separate files, Google access or customer records are needed. Run all cells with Python, pandas and matplotlib. Inputs come from the dated supervisor review and `outputs/model_validation/20261017_predictor_value/`; their SHA-256 hashes are stored in `saved_data['source_hashes']`.

The main removal tests used three chronological periods containing 2,478 validation service windows and 229 recorded returns, with earlier fitting/calibration and property/package separation. These historical data have already been explored, so results remain development evidence. Correlation uses a different, larger earlier dataset; it is not the same calculation as model validation.

All code cells were executed sequentially with a local Python harness and outputs saved. A native Jupyter kernel was unavailable; notebook structure was validated. The chart was inspected separately; native Jupyter page rendering was not verified.''')
    nb=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'},'execution_method':'Sequential Python harness; no native Jupyter kernel available.'})
    execute(nb);nbformat.validate(nb)
    path=OUT/'CP2_Model_Simple.ipynb';nbformat.write(nb,path)
    for cell in nb.cells:
        for output in cell.get('outputs',[]):
            if 'image/png' in output.get('data',{}):(OUT/'simple_predictor_chart.png').write_bytes(base64.b64decode(output.data['image/png']))
    print(json.dumps({'notebook':str(path),'executed_cells':sum(c.cell_type=='code' for c in cells),'all_variables':len(full),'self_contained':True}))

if __name__=='__main__':main()
