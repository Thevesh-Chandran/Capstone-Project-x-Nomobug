"""Fixed 2x4 candidate study, same original 100-row evaluation and OOF folds."""
from datetime import datetime,timezone
import json,joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits
import nbformat
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.compare_callback_blind_spots import folds
from scripts.test_calendar_note_predictors import PATTERNS,extract
from scripts.reconcile_callback_evidence import snapshot_known_by_service_end
from scripts.freeze_age_rain_candidate import RAIN
from scripts.research_expanded_targets import ROOT,save,sha
from scripts.build_supervisor_model_review import execute,export_html

OUT=ROOT/'outputs/model_validation/20261018_compact_notes_rain'
ORIGINAL=ROOT/'outputs/cp2-v2/model_corrected_v5/selected_ap'
NOTE=list(PATTERNS)+['notes_unknown']

def available_notes(f,raw):
    lookup=raw.set_index('calendar_event_row');rows=[]
    assert lookup.index.is_unique
    for idx,row in f.iterrows():
        if int(row.anchor_event_row) not in lookup.index:
            rows.append({'index':idx,**{k:np.nan for k in PATTERNS},'notes_unknown':1})
            continue
        event=lookup.loc[int(row.anchor_event_row)]
        date=pd.to_datetime(event.start_raw,utc=True).tz_convert('Asia/Kuala_Lumpur').tz_localize(None).normalize()
        timely=date==row.anchor_date and snapshot_known_by_service_end(event.to_dict())
        vals=extract(event.description) if timely else {k:np.nan for k in PATTERNS}
        rows.append({'index':idx,**vals,'notes_unknown':int(not timely)})
    return pd.DataFrame(rows).set_index('index')

def make_model(family,cols):
    categorical=[x for x in cols if x in b.CATEGORICAL];numeric=[x for x in cols if x not in categorical]
    p=c.make_pipeline('et10_leaf5',numeric);pre=p.steps[0][1]
    # Use only the predeclared compact categorical columns, not the global defaults.
    transformers=[]
    for name,transformer,fields in pre.transformers:
        fields=list(fields);transformers.append((name,transformer,categorical if set(fields)&set(b.CATEGORICAL) else numeric))
    pre.set_params(transformers=transformers)
    if family=='Random Forest':p.set_params(classifier=RandomForestClassifier(n_estimators=300,max_depth=6,min_samples_leaf=5,class_weight='balanced',random_state=42,n_jobs=2))
    return p

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protocol.json').exists():
        assert not list(OUT.glob('candidate_*.joblib')) and not (OUT/'results.json').exists(),'Preserve fitted study'
        save(OUT/'failed_preflight_protocol.json',json.loads((OUT/'protocol.json').read_text()))
    trainpath=ROOT/'outputs/cp2-v2/source_refresh_20260927/corrected_training/dataset_input.json';testpath=ROOT/'outputs/cp2-v2/source_refresh_20260927/new_mature_holdout/dataset_input.json'
    calendar=ROOT/'outputs/cp2-v2/source_refresh_20260927/old_calendar_private.json';extra=ROOT/'outputs/model_validation/20261018_frozen_age_rain/new_inputs_private.pkl'
    frame=c.prepare_input(b.load_dataset_input(trainpath));test=c.prepare_input(b.load_dataset_input(testpath))
    base=[v for v in b.BASE_NUMERIC if v!='location_uncertainty_radius_m']+list(b.PEST_CONTEXT_NUMERIC)+['normalized_pest_category','package_category','premise_type']
    base=list(dict.fromkeys(base));pre_rain=[v for v in b.WEATHER_NUMERIC if any(k in v for k in ['precipitation','rain','wet_days'])]
    variants={'Service + pest + history':base,'Add notes':base+NOTE,'Add rainfall':base+pre_rain+RAIN,'Add notes and rainfall':base+NOTE+pre_rain+RAIN}
    protected={str(p.relative_to(ROOT)):sha(p) for folder in [ORIGINAL,ROOT/'outputs/cp2-v2/prospective_callback_v2'] for p in folder.iterdir() if p.is_file()}
    save(OUT/'protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in [trainpath,testpath,calendar,extra]},'protected':protected,
        'question':'Recorded pest-related return within30days after a paid service','candidates':variants,'families':['Extra Trees300/depth10/leaf5','Random Forest300/depth6/leaf5'],'settings':'Balanced classes, seed42; no hyperparameter search.',
        'partitions':'Original5333historical fitting rows, original1978purged2025OOFvalidation observations; same100-service August2026 test. Missing notes do not remove rows.',
        'selection':'Highest pooled development average precision, tie F1; thresholds and Platt calibration from OOFvalidation only. Save all8artifacts and selection before test predictions.',
        'notes':'Same pinned refreshed Calendar snapshot as model input. Row identities checked against local service date. Require created/updated<=service end; otherwise notes unknown. Ten mention flags only, no raw personal/admin/medical/claim text used.',
        'limits':'Adaptive historical research on previously inspected100outcomes, only5returns. Simplification chosen from past studies, no independent final accuracy. Original history features and programme links retain their source limitations.'})
    raw=pd.DataFrame(json.loads(calendar.read_text(encoding='utf-8'))['records']);rain=pd.read_pickle(extra)[c.KEYS+RAIN]
    frame=frame.join(available_notes(frame,raw));test=test.join(available_notes(test,raw))
    frame=frame.merge(rain,on=c.KEYS,how='left',validate='one_to_one',indicator=True);test=test.merge(rain,on=c.KEYS,how='left',validate='one_to_one',indicator=True)
    assert frame._merge.eq('both').all() and test._merge.eq('both').all()
    frame=frame.drop(columns='_merge');test=test.drop(columns='_merge')
    train=frame[frame.outcome_end_date<pd.Timestamp('2026-08-15')];dev,_,_=c.reserved_split(frame);split=folds(dev)
    assert len(train)==5333 and len(test)==100
    coverage=[]
    for name,d in [('Training',train),('Test',test)]:coverage.append({'Partition':name,'Rows':len(d),'Returns':int(d[b.TARGET].sum()),'Timely notes':int(d.notes_unknown.eq(0).sum()),'Known interval rain':int(d.previous_interval_rain_mean_mm.notna().sum())})
    save(OUT/'coverage.json',coverage);manifest={};development=[]
    for family in ['Extra Trees','Random Forest']:
        for name,cols in variants.items():
            yy=[];pp=[]
            for fold,fit,val,audit in split:
                p=make_model(family,cols)
                with threadpool_limits(limits=2):p.fit(fit[cols],fit[b.TARGET]);prob=p.predict_proba(val[cols])[:,1]
                yy.extend(val[b.TARGET]);pp.extend(prob)
            cal,_=b.fit_calibrator(yy,pp);q=b.apply_calibrator(cal,pp);cut=b.select_threshold(yy,q);metrics=b.score(yy,q,cut)
            pipe=make_model(family,cols)
            with threadpool_limits(limits=2):pipe.fit(train[cols],train[b.TARGET])
            key=family+' / '+name;filename='candidate_'+str(len(manifest))+'.joblib'
            artifact={'pipeline':pipe,'features':cols,'calibrator':cal,'threshold':cut,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha(OUT/'protocol.json')};joblib.dump(artifact,OUT/filename)
            manifest[key]={'file':filename,'sha256':sha(OUT/filename),'threshold':cut,'inputs':len(cols),'frozen_at_utc':artifact['frozen_at_utc']}
            development.append({'candidate':key,**metrics});print('Frozen',key,flush=True)
    selected=max(development,key=lambda r:(r['average_precision'],r['f1']))
    save(OUT/'frozen_manifest.json',{'models':manifest,'selected_on_validation':selected['candidate'],'all_frozen_before_test':True})
    save(OUT/'development_results.json',development);results=[]
    for key,v in manifest.items():
        assert sha(OUT/v['file'])==v['sha256'];m=joblib.load(OUT/v['file'])
        with threadpool_limits(limits=2):p=b.apply_calibrator(m['calibrator'],m['pipeline'].predict_proba(test[m['features']])[:,1])
        tn,fp,fn,tp=confusion_matrix(test[b.TARGET],p>=m['threshold'],labels=[False,True]).ravel();met=b.score(test[b.TARGET],p,m['threshold'])
        results.append({'candidate':key,'selected_on_validation':key==selected['candidate'],'inputs':len(m['features']),'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),**met})
        pd.DataFrame({'actual':test[b.TARGET].to_numpy(),'probability':p}).to_csv(OUT/v['file'].replace('.joblib','_test.csv'),index=False)
    save(OUT/'results.json',results);assert all(sha(ROOT/p)==h for p,h in protected.items())
    save(OUT/'verification.json',{'frozen_originals_unchanged':True,'selected_before_assessment':selected['candidate'],'rows_assessed':len(test),'fits':32})
    report(results,coverage,selected['candidate']);print(json.dumps(results))

def report(results,coverage,selected):
    rows=[{'Candidate':r['candidate'],'Inputs':r['inputs'],'Chosen on validation':r['selected_on_validation'],'Accuracy %':100*r['accuracy'],'Precision %':100*r['precision'],'Recall %':100*r['recall'],'F1':r['f1'],'Correct alerts':r['TP'],'False alerts':r['FP'],'Missed returns':r['FN']} for r in results]
    nb=nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell('''# Service history, notes and rainfall — combined test
Eight fixed candidates: two algorithms × four input sets. Same original 100-service test, containing five returns. Thresholds and probability calibration use the original 2025 purged out-of-fold validation observations. The historical final fit has 5,333 mature service rows.

The compact baseline contains service stage/package/price, previous returns and visits, seasonality and pest types. Raw and normalized duplicate pest categories were reduced. Additions are ten safe Calendar mention flags plus an unknown flag; rainfall before the service, before first visit and between completed earlier visits.

All candidates were frozen before test predictions. The selected candidate was chosen on development average precision, not the highest test score. These historical outcomes were already inspected; five positives cannot establish reliable future performance.'''),nbformat.v4.new_markdown_cell('## Chosen using validation\n'+selected),nbformat.v4.new_code_cell('import pandas as pd\n'+f'display(pd.DataFrame({rows!r}).round(2))'),nbformat.v4.new_markdown_cell('## Coverage\nAll100testrowsremain, including unknown notes. Late-edited or missing notes are unknown, not a confirmed absence of pests.'),nbformat.v4.new_code_cell(f'display(pd.DataFrame({coverage!r}))'),nbformat.v4.new_markdown_cell('The original93-input comparison achieved94% accuracy,40% precision and40% recall on these same100records. The simplified models here answer the same30-day recorded-return question. No original model was overwritten. Mention flags are not verified observations or treatment completion. Code cells executed with the project harness; no native-kernel run.')])
    execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Notes_Rain_Combination.ipynb');export_html(nb,OUT/'Notes_Rain_Combination.html')

if __name__=='__main__':main()
