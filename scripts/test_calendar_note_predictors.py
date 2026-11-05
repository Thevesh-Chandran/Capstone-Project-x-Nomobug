"""Free-text Calendar note screening and earlier-period paired validation."""
from pathlib import Path
from datetime import datetime,timezone
import json,re
import numpy as np
import pandas as pd
import nbformat
from threadpoolctl import threadpool_limits
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.research_callback_targets import calibration_split,digest
from scripts.reconcile_callback_evidence import clean_text,snapshot_known_by_service_end
from scripts.build_supervisor_model_review import execute,export_html

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/model_validation/20261017_calendar_free_notes'
PEST=r'lipas|cockroach|roach|semut|ants?|tikus|rats?|rodent|pepijat|bed.?bug|nyamuk|mosquito|lalat|flies|infestation|perosak|pests?'
PATTERNS={
 'heavy_pest_mention':r'\b(?:banyak|bnyak|bnyk|teruk|heavy|high infestation|infestation high|severe)\b',
 'pest_improving_mention':r'\b(?:berkurang\w*|kurang|reduc\w*|improv\w*|less|sikit|sedikit)\b',
 'pest_persisting_mention':r'\b(?:masih|still|coming in|berulang)\b',
 'gel_bait_mention':r'\b(?:gel|bait\w*|umpan|advion)\b',
 'spray_mention':r'\b(?:spray\w*|sembur\w*)\b',
 'fog_mist_mention':r'\b(?:fog\w*|mist\w*)\b',
 'extra_dose_mention':r'\b(?:double|doubel|extra)\s+dos(?:e|age)\b',
 'treatment_restriction_mention':r'\b(?:cannot|can.t|jangan|taknak|tak boleh|elak\w*|avoid|no)\b.{0,65}\b(?:spray\w*|bait\w*|gel|sembur\w*)\b',
 'pest_evidence_mention':r'\b(?:droppings|tahi tikus|kesan gigit|gnaw\w*|egg\w*|telur|sarang|nest\w*)\b',
 'kitchen_drain_mention':r'\b(?:kitchen|dapur|drain\w*|longkang|manhole\w*|sinku|sink)\b',
}
LABELS={'heavy_pest_mention':'Heavy pest problem','pest_improving_mention':'Pest problem improving','pest_persisting_mention':'Pests still present','gel_bait_mention':'Gel or bait mentioned','spray_mention':'Spraying mentioned','fog_mist_mention':'Fogging or misting mentioned','extra_dose_mention':'Extra dosage mentioned','treatment_restriction_mention':'Treatment restriction','pest_evidence_mention':'Droppings, bites, eggs or nests','kitchen_drain_mention':'Kitchen or drainage context'}

def extract(text):
    lines=[]
    for line in clean_text(text).splitlines():
        line=line.lower().strip()
        if not line or '?' in line:continue # Template prompts are not observations.
        if re.match(r'^(?:nama|name|alamat|address|phone|tel|email|emel|invoice|payment|package|anggaran|estimated|saiz|size|date|time)\b',line):continue
        if re.search(r'@|\b\d{7,}\b|g6pd|pregnan|hamil|allerg|asthma|medical|student|teacher',line):continue
        if re.search(r'\b(?:warranty|claim|refund|cancel\w*|reschedul\w*|postpon\w*)\b',line):continue
        if re.search(r'\b(?:'+PEST+r'|spray\w*|bait\w*|gel|sembur\w*|fog\w*|mist\w*|dosage|droppings|sarang)\b',line):lines.append(line)
    result={name:0 for name in PATTERNS}
    for line in lines:
        for name,pattern in PATTERNS.items():
            if name in ['heavy_pest_mention','pest_improving_mention','pest_persisting_mention'] and not re.search(r'\b(?:'+PEST+r')\b',line):continue
            if re.search(pattern,line):result[name]=1
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True);assert not (OUT/'protocol.json').exists()
    source=ROOT/'outputs/cp2-v2/source_refresh_20260927/refreshed/dataset_input.json'
    evidence=ROOT/'outputs/cp2-v2/callback_evidence_reconciliation/source_private.json'
    frozen=ROOT/'outputs/cp2-v2/prospective_callback_v2';hashes={p.name:digest(p) for p in frozen.iterdir() if p.is_file()}
    protocol={'declared_utc':datetime.now(timezone.utc).isoformat(),'code_sha256':digest(Path(__file__)),'source_sha256':digest(source),'description_source_sha256':digest(evidence),'folds':b.DEVELOPMENT_FOLDS,'patterns':PATTERNS,'scope':'2025 development only; original model unchanged','rule':'Promising only if AP improves and Brier decreases in all three paired folds. Fixed et10_leaf5, calibration/threshold earlier partitions only.','semantics':'Mention flags, not verified treatment or severity. No raw text, names, contact, medical or claims fields fed to model.','frozen_hashes':hashes}
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    raw=json.loads(evidence.read_text());a=pd.DataFrame(raw['rows']['anchors']);a.anchor_date=pd.to_datetime(a.anchor_date)
    keys=['population','sales_record_id','anchor_date'];assert not a.duplicated(keys).any()
    extracted=pd.DataFrame([extract(v) for v in a.description]);a=pd.concat([a,extracted],axis=1)
    a['timely']=[snapshot_known_by_service_end(r) for r in raw['rows']['anchors']]
    f=c.prepare_input(b.load_dataset_input(source));f=f[f.anchor_date<pd.Timestamp('2026-01-01')].copy()
    original=len(f);f=f.merge(a[keys+list(PATTERNS)+['timely','target']],on=keys,how='inner',validate='one_to_one')
    assert f[b.TARGET].astype(int).eq(f.target.astype(int)).all()
    matched=len(f);f=f[f.timely].copy()
    coverage=[]
    for name in PATTERNS:
        coverage.append({'Input':LABELS[name],'All archived mentions':int(a[name].sum()),'Timely archived mentions':int(a.loc[a.timely,name].sum()),'Timely pre-2026 mentions':int(f[name].sum())})
    pd.DataFrame(coverage).to_csv(OUT/'note_coverage.csv',index=False)
    features=json.loads((frozen/'bundle.json').read_text())['models']['challenger_all_history']['features']
    groups={'Existing inputs':[], 'Pest condition notes':list(PATTERNS)[:3], 'Treatment and site notes':list(PATTERNS)[3:], 'All note inputs':list(PATTERNS)}
    rows=[];foldsupport=[]
    for fold,start,end in b.DEVELOPMENT_FOLDS:
        train,test,_=b.purged_split(f,start,end);fit,cal,_=calibration_split(train)
        foldsupport.append({'fold':fold,'fit':len(fit),'calibration':len(cal),'evaluated':len(test),'returns':int(test[b.TARGET].sum())})
        for variant,extra in groups.items():
            usable=[x for x in extra if fit[x].nunique()>1];columns=features+usable
            pipe=c.make_pipeline('et10_leaf5',[x for x in columns if x not in b.CATEGORICAL])
            with threadpool_limits(limits=2):
                pipe.fit(fit[columns],fit[b.TARGET],classifier__sample_weight=c.training_weights(fit,'standard'))
                calibrator,_=b.fit_calibrator(cal[b.TARGET],pipe.predict_proba(cal[columns])[:,1])
                threshold=b.select_threshold(cal[b.TARGET],b.apply_calibrator(calibrator,pipe.predict_proba(cal[columns])[:,1]))
                score=b.score(test[b.TARGET],b.apply_calibrator(calibrator,pipe.predict_proba(test[columns])[:,1]),threshold)
            rows.append({'fold':fold,'variant':variant,'extra_inputs':len(usable),'used_note_columns':'|'.join(usable),**score})
            pd.DataFrame(rows).to_csv(OUT/'fold_metrics.csv',index=False);print(fold,variant,'AP',round(score['average_precision'],4),flush=True)
    result=pd.DataFrame(rows);base=result[result.variant.eq('Existing inputs')].set_index('fold');summary=[]
    for variant,part in result.groupby('variant',sort=False):
        part=part.set_index('fold');wins=int(((part.average_precision>base.average_precision)&(part.brier_score<base.brier_score)).sum())
        summary.append({'Inputs':variant,'Correct warnings (%)':round(100*part.precision.mean(),1),'Returns detected (%)':round(100*part.recall.mean(),1),'F1 (%)':round(100*part.f1.mean(),1),'Average precision':round(part.average_precision.mean(),4),'Brier error':round(part.brier_score.mean(),4),'Periods improved on both':wins,'Decision':'Reference' if variant=='Existing inputs' else ('Promising; needs confirmation' if wins==3 else 'No consistent improvement')})
    pd.DataFrame(summary).to_csv(OUT/'comparison.csv',index=False)
    receipt={'pre2026_original':original,'matched':matched,'timely_eligible':len(f),'excluded_edited_later_or_unknown':matched-len(f),'fold_support':foldsupport,'archived_export_utc':raw.get('executed_at'),'frozen_unchanged':hashes=={p.name:digest(p) for p in frozen.iterdir() if p.is_file()}}
    assert receipt['frozen_unchanged'];(OUT/'acceptance.json').write_text(json.dumps(receipt,indent=2))
    md=nbformat.v4.new_markdown_cell;code=nbformat.v4.new_code_cell
    nb=nbformat.v4.new_notebook(cells=[md('# Can Calendar notes improve the prediction?\n\nFree-text notes do contain useful information missed by the earlier named-field-only check. We tested ten interpretable mention flags using the same model and three earlier validation periods. These describe what the text mentions, not confirmed treatment delivery.'),md(f'## Data used\n\nArchived export: {raw.get("executed_at")}. This is not a new live Calendar download. Of {original:,} pre-2026 model services, {matched:,} matched the note archive and {len(f):,} passed the timestamp gate. Both baseline and note models use exactly the same eligible rows. Latest notes edited after service end are excluded because their earlier wording is unavailable.'),code('import pandas as pd\nfrom io import StringIO\n'+f'display(pd.read_json(StringIO({pd.DataFrame(coverage).to_json(orient="records")!r})))'),md('## Model comparison\n\nScores are averages across the three periods. Correct warnings is precision; returns detected is recall. Higher average precision and lower Brier error are better. All thresholds were selected using earlier calibration data, never these validation outcomes.'),code(f'display(pd.read_json(StringIO({pd.DataFrame(summary).to_json(orient="records")!r})))'),code(f'display(pd.read_json(StringIO({pd.DataFrame(foldsupport).to_json(orient="records")!r})))'),md('## Interpretation and limits\n\nA promising addition must improve both ranking and probability error in every period. A small gain in one score is insufficient. The recent 2026 assessment and frozen prospective model are unchanged.\n\nRules exclude administrative/contact/medical/claim lines and template questions. Text mentions may still be incomplete, ambiguous or instructions for future treatment. Binary zero means the selected wording was not found, not that the condition was absent. Severity statements without a pest on the same line are conservatively missed.\n\nSnapshot edit times are a conservative historical proxy, not a full version history. Excluding later-edited events can select a different customer mix. These periods were previously explored; results are development evidence, not independent final accuracy. No raw descriptions are included in this report. Notebook executed sequentially in Python; native Jupyter kernel unavailable.')])
    nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
    for cell in nb.cells:
        if cell.cell_type=='code':cell.metadata['jupyter']={'source_hidden':True}
    execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Calendar_Notes_Test.ipynb');export_html(nb,OUT/'Calendar_Notes_Test.html')
    print(json.dumps(receipt,indent=2));print(pd.DataFrame(summary).to_string(index=False))

if __name__=='__main__':main()
