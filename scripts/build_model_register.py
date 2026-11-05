"""Source-indexed model register; no fitting, retuning or private-record export."""
from pathlib import Path
from datetime import datetime,timezone
import json,html,re,shutil,hashlib
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/model_validation/20261018_model_register'
ROOTS=[ROOT/'outputs/model_validation',ROOT/'outputs/additional_model_research',ROOT/'outputs/cp2-v2']
NAMES={'accuracy','precision','recall','f1','roc_auc','average_precision','brier_score','brier','mae','rmse','wape','pooled_accuracy','pooled_precision','pooled_recall','pooled_f1','mean_ap','mean_auc','mean_brier','mean_f1','mean_precision','mean_recall','Average precision','Brier error','Mean AP','Mean Brier','Mean precision','Mean recall','Mean F1','Accuracy (%)','Precision (%)','Recall (%)','F1 (%)','Accuracy %','Precision %','Recall %','F1 %','Correct warnings (%)','Returns detected (%)','Predicted returns correct (%)'}
META={'model','name','variant','candidate','family','policy','task','horizon_weeks','input_count','features','feature_set','inputs','Inputs','Inputs tested','Input group','Model','target','horizon','horizon_days','window_days','population','history','window','role','fold','period','Method','Version','rows','n','tested','services','Services','customers','positive_rows','positive_windows','positives','returns','Actual return windows','threshold','TP','FP','FN','TN','tp','fp','fn','tn','folds','origins','weeks','validation_services','positive_service_windows','Recorded returns','Tested programmes','test_services','test_returns'}

def normalize_metrics(raw):
    aliases={'Accuracy':['accuracy','pooled_accuracy','Accuracy (%)','Accuracy %'],
        'Precision':['precision','pooled_precision','Precision','Mean precision','mean_precision','Precision (%)','Precision %','Correct warnings (%)','Predicted returns correct (%)'],
        'Recall':['recall','pooled_recall','Recall','Mean recall','mean_recall','Recall (%)','Recall %','Returns detected (%)'],
        'F1':['f1','pooled_f1','Mean F1','mean_f1','F1 (%)','F1 %'],
        'AP':['average_precision','mean_ap','Average precision','Mean AP'],'Brier':['brier_score','brier','mean_brier','Brier error','Mean Brier'],
        'MAE':['mae'],'RMSE':['rmse'],'WAPE':['wape']}
    out={}
    for label,keys in aliases.items():
        for key in keys:
            value=raw.get(key)
            if isinstance(value,(int,float)) and not isinstance(value,bool):
                if label in ['Accuracy','Precision','Recall','F1']:
                    out[label+' %']=float(value) if '%' in key else float(value)*100
                elif label=='WAPE':out['WAPE %']=float(value)*100
                else:out[label]=float(value)
                break
    return out

def scalar_meta(raw):return {k:v for k,v in raw.items() if k in META and isinstance(v,(str,int,float,bool))}

def is_metrics(raw):return isinstance(raw,dict) and bool(set(raw)&NAMES) and any(isinstance(raw[k],(int,float)) for k in set(raw)&NAMES)

def status(path):
    s=str(path).replace('\\','/')
    if '/cp2-v2/' in s and '/model_corrected_v5/' not in s:return 'Legacy/research epoch; inspect source limitations'
    if 'development' in path.name or 'fold_metrics' in path.name or 'screen' in path.name:return 'Development/fold result; not independent final test'
    return 'Historical research; evaluation scope shown in source'

def read_sources():
    records=[];sources=[];excluded=[];features=[]
    def add(raw,p,locator,context):
        safe=scalar_meta(context)|scalar_meta(raw)
        fallback=locator.replace('$/','').replace('/',' · ').replace('_',' ')
        label=next((str(safe[k]) for k in ['model','Model','candidate','variant','family','name','Inputs tested','Input group','Inputs','Method'] if safe.get(k) is not None),fallback)
        metrics=normalize_metrics(raw)
        if not metrics:return
        row={'Study':str(p.parent.relative_to(ROOT/'outputs')),'Candidate':label,'Source':str(p.relative_to(ROOT)),
            'Location in source':locator,'Status':status(p),'Inputs / context':json.dumps(safe,ensure_ascii=False,default=str),**metrics}
        records.append(row)
    for folder in ROOTS:
        for p in sorted(folder.rglob('*')):
            if not p.is_file() or OUT in p.parents:continue
            if p.suffix not in ['.json','.csv']:continue
            name=p.name.lower()
            if any(t in name for t in ['private','predictions','dataset_input','scores','replay','snapshot','receipt','identities']):continue
            if not any(t in name for t in ['result','comparison','benchmark','candidate','fold_metric','removal','group_decision','development_','selection','protocol']):continue
            # DOSM's explicitly verified correction is nested under a failed first run.
            # The parent's marker excludes the initial files, not this separately
            # declared correction. Markers inside the corrected run still apply.
            corrected=ROOT/'outputs/model_validation/20261021_dosm_inputs/trusted_geography_v2'
            lineage=[p.parent,*p.parents]
            if p.is_relative_to(corrected):lineage=[a for a in lineage if a.is_relative_to(corrected)]
            invalid=next((a/'DO_NOT_USE.md' for a in lineage if a.is_relative_to(ROOT/'outputs') and (a/'DO_NOT_USE.md').exists()),None)
            if invalid:
                excluded.append({'Source':str(p.relative_to(ROOT)),'Reason':'Invalid run: '+str(invalid.relative_to(ROOT))});continue
            # Initial broad challenger folders superseded by explicitly verified reruns.
            if any(t in p.parts for t in ['broad_challenger_v1','first_service_challenger_v1']):
                excluded.append({'Source':str(p.relative_to(ROOT)),'Reason':'Superseded by verified rerun'});continue
            before=len(records)
            try:
                if p.suffix=='.csv':
                    df=pd.read_csv(p)
                    for i,raw in enumerate(df.where(pd.notna(df),None).to_dict('records')):add(raw,p,f'CSV row {i+2}',{})
                else:
                    data=json.loads(p.read_text(encoding='utf-8-sig'))
                    def walk(value,loc,context):
                        if isinstance(value,dict):
                            ctx=context|scalar_meta(value)
                            if isinstance(value.get('selected'),dict):ctx=ctx|scalar_meta(value['selected'])
                            if is_metrics(value):add(value,p,loc,context)
                            for key,v in value.items():
                                if key in ['features','numeric_feature_sets','feature_sets','feature_contracts','feature_groups','input_names','inputs','contracts'] and isinstance(v,(dict,list)):
                                    features.append({'Study':str(p.parent.relative_to(ROOT/'outputs')),'Source':str(p.relative_to(ROOT)),'Location':loc+'/'+key,'Declared input definitions':json.dumps(v,ensure_ascii=False,default=str)})
                                if key in ['records','predictions','per_row','examples']:continue
                                if isinstance(v,(dict,list)):walk(v,loc+'/'+str(key),ctx)
                        elif isinstance(value,list):
                            for i,v in enumerate(value):
                                if isinstance(v,(dict,list)):walk(v,loc+'/'+str(i),context)
                    walk(data,'$',{})
                if len(records)>before:sources.append({'Source':str(p.relative_to(ROOT)),'SHA256':hashlib.sha256(p.read_bytes()).hexdigest(),'Metric rows indexed':len(records)-before})
            except (ValueError,UnicodeError) as exc:excluded.append({'Source':str(p.relative_to(ROOT)),'Reason':'Read failure: '+type(exc).__name__})
    return records,sources,excluded,features

def curated():
    rows=[]
    def add(section,question,algorithm,variables,n,acc=None,prec=None,rec=None,note='',source=''):
        rows.append({'Section':section,'Prediction question':question,'Algorithm':algorithm,'Inputs':variables,'Test size':n,
            'Accuracy %':acc,'Precision %':prec,'Recall %':rec,'Interpretation':note,'Source':source})
    for dirname,section,n in [('20261018_original100_age_rain','Original 100-service comparison',100),('20261018_frozen_age_rain','Larger same-partition comparison',2075)]:
        p=ROOT/'outputs/model_validation'/dirname/'results.json'
        for r in json.loads(p.read_text()):
            name=r.get('Model',r.get('variant'));variables={'baseline':'Original 93 inputs','age':'93 + 2 neighbourhood-age inputs','rain':'93 + 6 rainfall inputs','age_and_rain':'93 + 2 age + 6 rain','Original baseline':'Original 93 inputs','Add age':'93 + 2 neighbourhood-age inputs','Add rainfall':'93 + 6 rainfall inputs','Add both':'93 + 2 age + 6 rain'}[name]
            add(section,'Recorded pest-related return within 30 days','Extra Trees: '+name,variables,n,100*r['accuracy'],100*r['precision'],100*r['recall'],'Same records within this section; historical comparison',str(p.relative_to(ROOT)))
    larger=ROOT/'outputs/model_validation/20261018_shortlist_larger/results.json'
    if larger.exists():
        for r in json.loads(larger.read_text()):
            add('Larger Random Forest shortlist','Recorded return within 30 days',r['candidate'],str(r['inputs'])+' fixed inputs',r['rows'],100*r['accuracy'],100*r['precision'],100*r['recall'],'Selected on validation' if r['selected_using_validation'] else 'Trade-off; no replacement promoted',str(larger.relative_to(ROOT)))
    compact=ROOT/'outputs/model_validation/20261018_compact_notes_rain/results.json'
    if compact.exists():
        for r in json.loads(compact.read_text()):
            add('Compact history + notes + rainfall','Recorded return within 30 days',r['candidate'],str(r['inputs'])+' inputs; see fixed candidate definitions',r['rows'],100*r['accuracy'],100*r['precision'],100*r['recall'],'Selected on validation' if r['selected_on_validation'] else 'Diagnostic candidate; not validation-selected',str(compact.relative_to(ROOT)))
    notes=ROOT/'outputs/model_validation/20261017_calendar_free_notes/pooled_results.csv'
    for r in pd.read_csv(notes).to_dict('records'):
        add('Calendar notes','Recorded pest-related return within 30 days','Extra Trees',r['Model'],r['Services'],r['Accuracy (%)'],r['Precision (%)'],r['Recall (%)'],'Pooled three earlier periods; notes are mentions, not confirmed treatment',str(notes.relative_to(ROOT)))
    for dirname,label in [('20261017_interservice_weather_v2','Weather between visits'),('20261017_before_first_weather','Weather before first visit')]:
        p=ROOT/'outputs/model_validation'/dirname/'comparison.csv';d=pd.read_csv(p);r=d.sort_values('f1',ascending=False).iloc[0]
        add(label,'Return within 30 days after third residential 3x visit',r['model'],r['features'],int(r['tested']),100*r['accuracy'],100*r['precision'],100*r['recall'],'Highest inspected F1 in this study; not independent winner',str(p.relative_to(ROOT)))
    p=ROOT/'outputs/model_validation/20261016_target_research/comparison.csv';df=pd.read_csv(p)
    for (h,t,pop),part in df.groupby(['horizon','target','population']):
        valid=part[part.folds.ge(3)]
        if valid.empty:continue
        r=valid.sort_values('pooled_f1',ascending=False).iloc[0]
        add('Alternative pest-return targets',f'{pop}: return within {h} days after {t}',r['model'],r['features'],int(r['services']),100*r['pooled_accuracy'],100*r['pooled_precision'],100*r['pooled_recall'],'Highest inspected historical F1 for this question; targets differ',str(p.relative_to(ROOT)))
    p=ROOT/'outputs/model_validation/20261018_expanded_targets/repeat_results.json'
    for r in json.loads(p.read_text()):
        m=r['assessment'];s=r['selected'];add('Repeat purchases',r['question'],s['model'],', '.join(r['inputs']),m['n'],100*m['accuracy'],100*m['precision'],100*m['recall'],'First recorded purchase; chronological assessment',str(p.relative_to(ROOT)))
    p=ROOT/'outputs/model_validation/20261018_expanded_targets/customer_history/results.json'
    for r in json.loads(p.read_text()):
        if r['policy']!='precision':continue
        m=r['assessment'];add('Repeat purchases',f"Another distinct programme within {r['horizon']} days after any purchase",r['selected']['model'],', '.join(r['input_names']),m['n'],100*m['accuracy'],100*m['precision'],100*m['recall'],'Allows past purchases by same customer; grouped uncertainty',str(p.relative_to(ROOT)))
    p=ROOT/'outputs/model_validation/20261017_variable_selection/later_comparison.csv'
    for r in pd.read_csv(p).to_dict('records'):
        if r['Version']!='selected':continue
        add('Variable selection','Return after third residential 3x visit',r['Method'],'2 inputs: pest category and rodent indicator at final visit',r['Tested programmes'],r['Accuracy (%)'],r['Predicted returns correct (%)'],r['Returns detected (%)'],'F1 below always-yes comparator',str(p.relative_to(ROOT)))
    p=ROOT/'outputs/model_validation/20261021_precision_targets_v2/results.json'
    if p.exists():
        for r in json.loads(p.read_text()):
            add('21 October: return targets',r['target']+' / '+r['policy'],r['family'],str(r['input_count'])+' fixed inputs',r['rows'],100*r['accuracy'],100*r['precision'],100*r['recall'],'Globally group-separated selection; corrected adaptive historical research; no promotion',str(p.relative_to(ROOT)))
    p=ROOT/'outputs/model_validation/20261021_renewal_targets/results.json'
    if p.exists():
        for r in json.loads(p.read_text()):
            if r['policy']!='precision':continue
            m=r['assessment'];s=r['selected']
            add('21 October: customer-month repurchase',f"{r['population']}: purchase within {r['horizon']} days",s['model'],str(s['input_count'])+' past-only inputs',m['n'],100*m['accuracy'],100*m['precision'],100*m['recall'],'Overlapping customer-months, small positive customer support; no promotion',str(p.relative_to(ROOT)))
    p=ROOT/'outputs/model_validation/20261021_enquiry_conversion/results.json'
    if p.exists():
        d=json.loads(p.read_text())
        for r in d['results']:
            m=r['assessment'];s=r['selected'];add('21 October: enquiries',d['question']+' / '+r['policy'],s['model'],'7 initial-reply fields',m['n'],100*m['accuracy'],100*m['precision'],100*m['recall'],'Recorded-sale linkage proxy; no promotion',str(p.relative_to(ROOT)))
    p=ROOT/'outputs/model_validation/20261021_dosm_inputs/trusted_geography_v2/portable_aggregate.json'
    if p.exists():
        d=json.loads(p.read_text())
        for r in d['results']:
            add('21 October: new DOSM data','Recorded return within 30 days','Extra Trees: '+r['candidate'],str(r['input_count'])+' inputs',r['rows'],100*r['accuracy'],100*r['precision'],100*r['recall'],'Same larger partition; trusted district2022 context/CPI; small trade-off, no promotion',str(p.relative_to(ROOT)))
    p=ROOT/'outputs/model_validation/20261021_management_forecasts_v2/results.json'
    if p.exists():
        for r in json.loads(p.read_text()):
            add('21 October: booking planning',f"{r['target']}: next {r['horizon_weeks']} weeks",r['selected']['family'],str(r['input_count'])+' fields',r['assessment']['origins'],note=f"MAE {r['assessment']['mae']:.2f} vs baseline {r['baseline_assessment']['mae']:.2f}; research gate {r['research_gate_passed']}. Timestamp-filtered surviving records; not proven live.",source=str(p.relative_to(ROOT)))
    return rows

def main():
    OUT.mkdir(parents=True,exist_ok=True);records,sources,excluded,features=read_sources();summary=curated()
    for name,data in [('All_Saved_Results.csv',records),('Study_Summary.csv',summary),('Source_Index.csv',sources),('Excluded_Runs.csv',excluded),('Declared_Input_Lists.csv',features)]:pd.DataFrame(data).to_csv(OUT/name,index=False)
    variables=ROOT/'outputs/supervisor_model_review/20261017/data/variables_plain_english.csv';shutil.copy2(variables,OUT/'Original_93_Inputs_Explained.csv')
    dictionary=pd.read_csv(variables).to_dict('records')
    payload=json.dumps({'records':records,'variables':dictionary,'sources':sources},ensure_ascii=False,default=str,allow_nan=False).replace('<','\\u003c')
    forecasts=json.loads((ROOT/'outputs/model_validation/20261018_expanded_targets/forecast_results.json').read_text())
    fr=[{'Target':r['target'],'Model':r['selected']['model'],'Inputs':r['selected']['inputs'],'Test weeks':r['assessment']['weeks'],'Model MAE':round(r['assessment']['mae'],2),'Baseline':r['baseline_selection']['model'],'Baseline MAE':round(r['baseline_assessment']['mae'],2)} for r in forecasts]
    sections=[]
    for section,part in pd.DataFrame(summary).groupby('Section',sort=False):
        cols=['Prediction question','Algorithm','Inputs','Test size','Accuracy %','Precision %','Recall %','Interpretation']
        sections.append('<h2>'+html.escape(section)+'</h2>'+part[cols].round(2).fillna('').to_html(index=False,border=0,escape=True))
    page='''<!doctype html><html><meta charset="utf-8"><title>CP2 — all tested models</title><style>
body{margin:0;background:#f4f6fa;color:#172033;font:15px/1.6 Arial}main{max-width:1400px;margin:auto;padding:40px}h1{font-size:34px}h2{margin-top:40px}p{max-width:1000px}table{border-collapse:collapse;width:100%;font-size:13px;background:white}th,td{padding:10px;text-align:left;border-bottom:1px solid #e2e8f0;vertical-align:top}th{background:#eaf0fa;position:sticky;top:0}td{max-width:460px;overflow-wrap:anywhere}section{overflow:auto;background:white;border:1px solid #dce2eb;padding:24px;border-radius:10px;margin:24px 0}.tag{background:#eaf0fa;padding:12px 18px;border-left:4px solid #2563eb}input,select,button{font:inherit;padding:10px;border:1px solid #cbd5e1;border-radius:6px;margin:4px}input{width:420px}a{color:#1d4ed8}.scroll{overflow:auto;max-height:650px}.small{font-size:13px;color:#526078}details{margin:18px 0}summary{cursor:pointer;font-weight:bold}</style><main>
<h1>All tested models — questions, inputs and results</h1><p>Updated 21 October 2026. <a href="../20261021_management_model_search/Management_Model_Search.html">Start with the latest plain-language comparison</a>, then use the searchable saved-results register for indexed variants, thresholds and folds.</p>
<p class="tag"><b>There is no single comparable “best accuracy”.</b> Compare models only within the same question, population and evaluation records. Original100-service precision40% and larger2,075-service precision23% come from different fitting/evaluation setups. Accuracy, precision and recall are percentages; AP and Brier in the full register retain their original scale.</p>
<h2>Algorithms actually tested</h2><p>Logistic regression (ordinary and class-balanced), Random Forest, Extra Trees, histogram gradient boosting, CatBoost, tree ensembles/blends; forecasting also used Ridge, Poisson regression, simple exponential smoothing, damped Holt, last-week, moving-average and seasonal baselines. Different depth, leaf-size, weighting, input and training-history configurations appear in the complete register.</p>
<h2>Inputs in plain language</h2><p><b>Original93:</b> package/service stage and price; pest types; client/premises information; earlier property/package/area return history; rainfall/temperature/humidity/soil moisture before service; water/drain/forest proximity, elevation and location uncertainty; derived interactions. The full93-field dictionary is below.</p>
<p><b>New age:</b>1kmneighbourhood settlement-age code and unknown flag. <b>New rain:</b> mean rain between earlier visits, since first visit, interval length/unknown flag, and7/30-day rain before first visit. <b>Other studies:</b> Calendar pest/treatment mentions; team continuity; historical food nodes; district population; festival/weekday context; previous customer purchases and lagged weekly activity. <b>21 October:</b> advance booking stock, enquiry initial fields, district2022 household income/spending/poverty, and CPI lagged by two months. Published input definitions are indexed in the downloadable file.</p>
<p><a href="Study_Summary.csv">Study summary CSV</a> · <a href="All_Saved_Results.csv">All saved metric rows CSV</a> · <a href="Declared_Input_Lists.csv">Declared input lists</a> · <a href="Original_93_Inputs_Explained.csv">Original93 dictionary</a> · <a href="Source_Index.csv">Source/hash index</a> · <a href="Excluded_Runs.csv">Excluded/failed runs</a></p><section>'''+''.join(sections)+'''</section><section><h2>Earlier 18 October forecasts — errors, not classification percentages</h2>'''+pd.DataFrame(fr).to_html(index=False,border=0)+'''<p>MAE is average error in bookings, packages or RM. These earlier selected models lost to their development-selected simple baselines. The separate 21 October planning forecasts above test advance booking stock and later additions; two passed an exploratory research gate. All remain historical evidence.</p></section>
<section><h2>Complete searchable register</h2><p class="small">Rows include model summaries, folds, thresholds, feature-removal tests and duplicated published summaries. A row is not necessarily a distinct trained model or independent experiment. Legacy results retain their original source epoch; inspect its limitations before citing. Invalid runs and unverified superseded challengers are excluded.</p>
<input id="query" placeholder="Search: rainfall, flood, 60, catboost, notes…"><select id="study"><option value="">All studies</option></select><button id="prev">Previous</button><button id="next">Next</button><p id="count"></p><div class="scroll"><table id="registry"></table></div></section>
<section><h2>Every original input explained</h2><p>Observed relationships do not prove causality, statistical significance or predictive value. Separate group-removal and individual-removal results are in the register.</p><div class="scroll" id="dictionary"></div></section>
<section><h2>How to interpret the evidence</h2><p>Original frozen future-test outcomes remain pending. These historical periods have been examined during development. Hypothesis searches, different targets and repeated variants cannot establish new independent prospective accuracy. A larger score from a different population or target is not proof of a better model.</p><p>For legacy runs, the underlying source epoch and earlier data-quality limitations remain. The register indexes saved evidence without certifying every legacy score as current or valid. Per-fold, period-average and pooled results are distinct. Some older top20% metrics describe ranking, not a yes/no decision; their source context remains visible.</p><p>Only aggregate metadata/metrics and the variable glossary are exported. No customer names, addresses, contacts or per-customer predictions are included.</p></section></main><script>
const data=PAYLOAD;let page=0;const q=document.getElementById('query'),s=document.getElementById('study');
function table(element,rows,columns){element.replaceChildren();const head=document.createElement('tr');columns.forEach(c=>{let th=document.createElement('th');th.textContent=c;head.append(th)});element.append(head);rows.forEach(row=>{let tr=document.createElement('tr');columns.forEach(c=>{let td=document.createElement('td'),v=row[c];td.textContent=typeof v==='number'?v.toFixed(3):v??'';tr.append(td)});element.append(tr)})}
[...new Set(data.records.map(r=>r.Study))].sort().forEach(v=>{let o=document.createElement('option');o.value=v;o.textContent=v;s.append(o)})
function draw(){const text=q.value.toLowerCase();let rows=data.records.filter(r=>(!s.value||r.Study===s.value)&&JSON.stringify(r).toLowerCase().includes(text));page=Math.min(page,Math.max(0,Math.ceil(rows.length/75)-1));table(document.getElementById('registry'),rows.slice(page*75,(page+1)*75),['Study','Candidate','Accuracy %','Precision %','Recall %','F1 %','AP','Brier','MAE','Inputs / context','Status','Source','Location in source']);document.getElementById('count').textContent=rows.length+' matching saved result rows · page '+(page+1)+' of '+Math.max(1,Math.ceil(rows.length/75))}
q.oninput=s.onchange=()=>{page=0;draw()};document.getElementById('prev').onclick=()=>{page=Math.max(0,page-1);draw()};document.getElementById('next').onclick=()=>{page++;draw()};draw();let t=document.createElement('table');table(t,data.variables,['Variable','What it means','Type','Group','Technical field']);document.getElementById('dictionary').append(t);
</script></html>'''
    page=page.replace('PAYLOAD',payload)
    # Improve prose spacing without changing code identifiers, dataset keys or paths.
    page=page.replace('Original100-service','Original 100-service').replace('larger2,075','larger 2,075').replace('Original93','Original 93').replace('original93','original 93').replace('full93','full 93').replace('1kmneighbourhood','1 km neighbourhood').replace('and7/30','and 7/30')
    (OUT/'All_Models_Explained.html').write_text(page,encoding='utf-8')
    manifest={'built_at_utc':datetime.now(timezone.utc).isoformat(),'metric_rows':len(records),'source_files':len(sources),'excluded_files':len(excluded),'summary_rows':len(summary),'input_definition_records':len(features),'unique_trained_model_count':'Not inferred from metric rows; repeated thresholds/folds/summaries are indexed separately.'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest))
    # Keep the portable notebook and share ZIP in sync with regenerated CSVs.
    import os,zipfile,nbformat
    from scripts.build_supervisor_model_review import execute,export_html
    nb=nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell(f'# All tested models — study summary\n\nUpdated 21 October 2026. This notebook shows {len(summary)} source-backed study summary rows. The searchable HTML and All_Saved_Results.csv index variants, thresholds and folds; their rows are not a count of independent models.\n\nCompare only within the same target and evaluation population. Start with the separate 21 October management-model-search notebook for the latest recommendation.'),
        nbformat.v4.new_code_cell("import pandas as pd\nfrom pathlib import Path\nfolder=Path.cwd()\nif not (folder/'Study_Summary.csv').exists():\n    folder=Path('outputs/model_validation/20261018_model_register')\nassert (folder/'Study_Summary.csv').exists(), 'Open this notebook with its accompanying CSVs.'\nsummary=pd.read_csv(folder/'Study_Summary.csv')\nfor section,part in summary.groupby('Section',sort=False):\n    print(section)\n    display(part.drop(columns=['Source','Section']).round(2).fillna(''))"),
        nbformat.v4.new_markdown_cell('## Full variants and inputs\n\nOpen All_Models_Explained.html for search and pagination. Exact input lists and the original 93-input glossary are alongside it. Older epochs retain their source limitations. No fitting or operational changes are performed by this notebook. Cells executed sequentially with the existing Python harness; no native Jupyter kernel was available.')])
    nb.metadata['kernelspec']={'display_name':'Python 3','language':'python','name':'python3'}
    prior=Path.cwd()
    try:
        os.chdir(OUT);execute(nb)
    finally:os.chdir(prior)
    nbformat.validate(nb);nbformat.write(nb,OUT/'Model_Register.ipynb');export_html(nb,OUT/'Model_Register_Notebook.html')
    names=['All_Models_Explained.html','Model_Register.ipynb','Model_Register_Notebook.html','All_Saved_Results.csv','Study_Summary.csv','Declared_Input_Lists.csv','Original_93_Inputs_Explained.csv','Source_Index.csv','Excluded_Runs.csv','manifest.json']
    with zipfile.ZipFile(OUT/'Model_Register_Share.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in names:archive.write(OUT/name,name)

if __name__=='__main__':main()
