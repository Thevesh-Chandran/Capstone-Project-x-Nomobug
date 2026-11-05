"""Publish a plain-language, complete predictor guide from audited aggregates."""
from pathlib import Path
import html, json, re, zipfile
import pandas as pd
import nbformat
from scripts.build_supervisor_model_review import execute, export_html

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/supervisor_model_review/20261017'

def explain(n):
    fixed={
      'service_number':('Service number','Which paid visit this is: first, second, third, etc.'),
      'package_sessions_recorded':('Services in package','Number of paid visits recorded for the package.'),
      'sale_total_rm':('Package price (RM)','Recorded sale price; not cash received or profit.'),
      'days_sale_to_anchor':('Days from sale to visit','Elapsed days between the sale and this service.'),
      'days_since_previous_service':('Days since previous visit','Recorded gap since the previous service.'),
      'days_since_prior_property_claim':('Days since last recorded return','Time since the last corrective return recorded at this property.'),
      'anchor_is_first':('First visit?','1 for the first paid visit; 0 otherwise.'),
      'anchor_is_final':('Last paid visit?','1 when this is the final recorded paid visit in the package.'),
      'anchor_is_single_service':('One-visit package?','1 for a package containing one paid service.'),
      'anchor_is_mixed_pest':('Multiple pest types?','1 when at least two known pest types are recorded.'),
      'anchor_remaining_services':('Paid visits remaining','Package visits minus the current service number.'),
      'anchor_service_progress':('Package progress','Current service number divided by the number of package visits.'),
      'anchor_month_sin':('Service month — seasonal input A','Sine of month; used with input B so December and January are treated as neighbours.'),
      'anchor_month_cos':('Service month — seasonal input B','Cosine of month; paired with input A. Neither alone means earlier or later months.'),
      'premise_type':('Client / premises type','Recorded residential or commercial context.'),
      'pest_category':('Recorded pest category','Pest category from the prepared service record.'),
      'normalized_pest_category':('Standardised pest category','Pest text grouped into consistent categories, including mixed and unknown.'),
      'calendar_pest_text_category':('Pest mentioned in appointment','Category extracted from Calendar pest text.'),
      'calendar_service_method_category':('Treatment method','Recorded treatment-method category from Calendar text.'),
      'package_category':('Package type','Recorded package category.'),
      'pest_distinct_known_types':('Number of pest types','Count of distinct recognised pest types in the record.'),
      'location_uncertainty_radius_m':('Location uncertainty (metres)','Estimated positional uncertainty; larger means a less precise location.'),
      'elevation_m':('Elevation (metres)','Ground height above sea level.'),
      'local_relief_500m_m':('Nearby height variation (metres)','Terrain-height variation within 500 metres.'),
      'log1p_waterway_distance':('Transformed distance to waterway','Logarithm of 1 + waterway distance in metres; reduces the influence of very large distances.'),
      'water_rain_interaction':('Rain combined with waterway proximity','14-day rain / (1 + waterway distance in kilometres). Larger with more rain or closer water.'),
      'drainage_rain_interaction':('Rain combined with drain proximity','14-day rain / (1 + drainage distance in kilometres).'),
      'rain_soil_interaction':('Rain combined with soil moisture','14-day rain multiplied by 7-day average surface soil moisture.'),
      'first_service_no_property_history':('First visit with no recorded history?','1 for a first paid visit with no earlier recorded property service.'),
      'first_service_prior_property_return_rate':('Past return ratio on first visit','Adjusted property return ratio on first visits; zero on other stages.'),
      'mixed_pest_prior_property_return_rate':('Past return ratio for multiple pests','Adjusted property return ratio for mixed-pest records; zero otherwise.'),
      'first_service_rain_14d':('Rain before first visit','14-day rain on first visits; zero on other stages.'),
      'mixed_pest_rain_14d':('Rain with multiple pest types','14-day rain for mixed-pest records; zero otherwise.'),
      'days_since_last_rain_1mm_capped_30d':('Days since rain','Days since at least 1 mm of daily rain, capped at 30 days.'),
    }
    if n in fixed:return fixed[n]
    for prefix,stage in [('first_pest_','first paid visit'),('final_pest_','last paid visit')]:
        if n.startswith(prefix):
            pest=n[len(prefix):].replace('_',' ')
            return (f'{pest.title()} at {stage}?',f'1 when {pest} is recorded AND this is the {stage}; 0 otherwise.')
    if n.startswith('pest_has_'):
        pest=n[9:].replace('_',' ')
        return (f'{pest.title()} recorded?',f'1 when the record mentions {pest}; 0 otherwise. Absence of a mention is not proof of absence.')
    if n.startswith('hotosm_nearest_') or n.startswith('nearest_mapped_'):
        kind=n.replace('hotosm_nearest_','').replace('nearest_mapped_','').removesuffix('_m').replace('_',' ')
        return (f'Distance to mapped {kind} (metres)',f'Distance to the nearest mapped {kind}; map coverage may be incomplete.')
    if n.startswith('hotosm_water_features_'):
        radius=n.split('_')[-1]
        return (f'Water features within {radius}',f'Count of mapped water features within {radius} of the location.')
    if n.startswith(('prior_property_','prior_package_','prior_area_')):
        scope=n.split('_')[1];s=n[len('prior_'+scope+'_'):]
        labels={'warranty_claims':'Recorded earlier returns','service_events':'Recorded earlier services','claims_90d':'Recorded returns in previous 90 days','services_90d':'Recorded services in previous 90 days','return_rate_smoothed':'Adjusted past return ratio'}
        label=labels[s]+' — '+scope
        desc=f'Count of earlier recorded {"corrective return visits" if "claim" in s else "service events"} for this {scope}'+(' in the previous 90 days.' if '90d' in s else '.')
        if s=='return_rate_smoothed':desc=f'(Earlier {scope} returns + 1) / (earlier {scope} services + 10). Adjusted ratio, not a literal infestation rate.'
        return label,desc
    m=re.match(r'prior_(\d+)d_(.*)',n)
    if m:
        days,kind=m.groups()
        meanings={'precipitation_mm':'Total rain (mm)','heavy_rain_days_10mm':'Days with at least 10 mm rain','max_daily_precipitation_mm':'Highest daily rain (mm)','wet_days_1mm':'Days with at least 1 mm rain','relative_humidity_mean_pct':'Average relative humidity (%)','soil_moisture_0_to_7cm_mean':'Average surface soil moisture (top 7 cm)','temperature_max_c':'Maximum temperature (°C)','temperature_mean_c':'Average temperature (°C)','vs_previous_11d_daily_rain_trend_mm':'Recent rain trend (mm/day)'}
        label=meanings[kind]+f' — previous {days} days'
        desc=f'{meanings[kind]} measured before the service, across the previous {days} days.'
        if kind.startswith('vs_'):desc='Average daily rain in the previous 3 days minus average daily rain in the preceding 11 days.'
        return label,desc
    raise ValueError('Missing plain-language definition: '+n)

def main():
    dictionary=pd.read_csv(OUT/'data/predictor_dictionary.csv')
    numeric=pd.read_csv(OUT/'data/numeric_associations.csv').set_index('feature')
    rows=[]
    for r in dictionary.to_dict('records'):
        n=r['predictor'];label,meaning=explain(n)
        rho=numeric.loc[n,'spearman_rho'] if n in numeric.index else float('nan')
        if n not in numeric.index:effect='Depends on category; no single up/down direction.'
        elif pd.isna(rho):effect='Cannot measure: no variation or insufficient values.'
        else:effect=('Higher values linked to more returns' if rho>0 else 'Higher values linked to fewer returns')+f' (correlation {rho:+.3f}).'
        if pd.notna(rho) and abs(rho)<.1:effect+=' Very small relationship.'
        rows.append({'Variable':label,'What it means':meaning,'Type':r['type'],'Observed relationship':effect,'Missing (%)':round(r['missing_pct'],1),'Group':r['group'],'Technical field':n})
    guide=pd.DataFrame(rows);assert len(guide)==93 and guide.Variable.nunique()==93
    guide.to_csv(OUT/'data/variables_plain_english.csv',index=False)
    summary='''# What the model uses — plain-English guide
The question is: **Will a recorded pest-related return occur within 30 days after this paid service?** The label is a recorded return, not proof of biological pest recurrence or a verified formal warranty claim.

There are **93 input variables**, expanded to **238 columns** inside the model. Many are alternative versions of the same information: service stage, pest type, past visits, rain and nearby water. They are not 93 independent causes.

## How to read the table
**Observed relationship** shows what happened in 5,333 earlier service records (492 recorded returns). Positive correlation means higher values accompanied more returns; negative means fewer. Near zero means little monotonic relationship. These are associations, not the model's individual decision rules.

**Statistical significance:** not established here. Repeated properties and overlapping service windows mean an ordinary independent-row p-value would be misleading. **Contribution to model performance:** also not established for each variable by this table. That requires a separate validation comparison with and without the variable; correlations cannot substitute for it.

The clearest measured associations include fewer remaining visits (−0.223), higher service number (+0.220), and package progress (+0.218). These overlap. Rain over the preceding 14 days has a very small relationship (+0.014). This does not show that rain improves predictions. The adjusted history ratio has a negative relationship partly entangled with its service-count denominator; it does not mean pest history protects a building.

## Every variable used by the frozen 30-day model
'''
    nb=nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell(summary),nbformat.v4.new_code_cell("from pathlib import Path\nimport pandas as pd\nBASE=Path.cwd()\nif not (BASE/'data/variables_plain_english.csv').exists():\n    BASE=BASE/'outputs/supervisor_model_review/20261017'\nvariables=pd.read_csv(BASE/'data/variables_plain_english.csv')\nassert len(variables)==93\nfor group,part in variables.groupby('Group',sort=False):\n    print(group)\n    display(part.drop(columns=['Group','Technical field']))"),nbformat.v4.new_markdown_cell('''## What is not included
Building age and verified building-wide pest history are **not available**. Existing past-return variables describe recorded property/package events. They do not capture every infestation in a building.

## Current result
The earlier 100-service test contained 5 returns: the model caught 2, missed 3 and raised 3 false alarms. Accuracy was **94%**, versus **95%** from always saying no return. Recall and precision were both **40%**. It remains experimental.

## Separate 60-day research model
This asks about a return within 60 days after the final residential paid service. It uses 23 inputs, not all 93. The list below is separate; the correlations above are not evidence for that different target.'''),nbformat.v4.new_code_cell("research=pd.read_csv(BASE/'data/research60_predictors.csv')\nlookup=variables.set_index('Technical field')\nresearch['Variable']=research.research60_predictor.map(lookup.Variable)\nresearch['What it means']=research.research60_predictor.map(lookup['What it means'])\nassert len(research)==23 and research.Variable.notna().all()\ndisplay(research[['Variable','What it means']])"),nbformat.v4.new_markdown_cell('Technical names, source hashes, partition details and the earlier analysis remain in CP2_Model_Review.html and the data folder. No model weights, thresholds or future-test records were changed.')],metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'},'execution_method':'Sequential Python harness; no native Jupyter kernel available.'})
    execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'START_HERE_Variables.ipynb')
    export_html(nb,OUT/'START_HERE_Variables.html')
    p=OUT/'START_HERE_Variables.html';s=p.read_text(encoding='utf-8')
    s=s.replace('<body>','<body><label>Find a variable <input id="find" placeholder="Try rain, cockroach, price…" style="padding:12px;width:300px"></label>')
    s += '<script>document.getElementById("find").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script>'
    p.write_text(s,encoding='utf-8')
    (OUT/'README.txt').write_text('START HERE: START_HERE_Variables.html\nPlain-English definitions and measured associations for all 93 frozen-model inputs.\nNotebook: START_HERE_Variables.ipynb (two cells executed using a sequential Python harness).\nTechnical appendix: CP2_Model_Review.html / .ipynb.\nNo private customer rows, model changes or new accuracy claims.\nHTML browser visual preview unavailable under current file-URL policy; content and notebook execution checked.\n',encoding='utf-8')
    import hashlib
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((OUT/'data').iterdir()) if p.name!='manifest.json'}
    (OUT/'data/manifest.json').write_text(json.dumps(manifest,indent=2))
    with zipfile.ZipFile(OUT/'CP2_Supervisor_Review.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in [*OUT.glob('*.html'),*OUT.glob('*.ipynb'),OUT/'README.txt',*sorted((OUT/'data').glob('*'))]:z.write(p,p.relative_to(OUT))
    print('Verified: 93 unique explained variables; 23 separate research variables; 2 executed notebook cells.')

if __name__=='__main__':main()
