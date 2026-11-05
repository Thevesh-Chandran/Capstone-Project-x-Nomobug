"""Fixed RF shortlist vs reproduced 93-input baseline on larger historical split."""
from datetime import datetime,timezone
import json,joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits
import nbformat
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.evaluate_larger_frozen_model import make_partitions,bootstrap_intervals
from scripts.test_compact_notes_rain import available_notes,make_model
from scripts.research_expanded_targets import ROOT,save,sha
from scripts.build_supervisor_model_review import execute,export_html

OUT=ROOT/'outputs/model_validation/20261018_shortlist_larger'
ORIGINAL=ROOT/'outputs/cp2-v2/prospective_callback_v2'

def main():
    OUT.mkdir(parents=True,exist_ok=True);assert not (OUT/'protocol.json').exists(),'Keep declared study'
    source=ROOT/'outputs/cp2-v2/source_refresh_20260927/refreshed/dataset_input.json'
    calendar=ROOT/'outputs/cp2-v2/source_refresh_20260927/old_calendar_private.json'
    shortlist=ROOT/'outputs/model_validation/20261018_compact_notes_rain/protocol.json'
    baselinepath=ROOT/'outputs/model_validation/20261017_larger_frozen_test/larger_historical_model.joblib'
    protected={str(p.relative_to(ROOT)):sha(p) for p in ORIGINAL.iterdir() if p.is_file()}
    previous=json.loads(shortlist.read_text());contracts={'Random Forest 28':previous['candidates']['Service + pest + history'],
        'Random Forest notes 39':previous['candidates']['Add notes']}
    save(OUT/'protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),
        'sources':{str(p.relative_to(ROOT)):sha(p) for p in [source,calendar,shortlist,baselinepath]},'protected':protected,
        'target':'Recorded pest-related return within30days after paid service','contracts':contracts,
        'models':'Shortlisted RF settings unchanged:300trees,max_depth6,min_leaf5,balanced,seed42. Existing93-input larger baseline artifact replayed.',
        'partition':'Same fixed property/package-disjoint train1506,validation1177,assessment2075 with outcome gaps; no rows removed for notes availability.',
        'calibration':'Fit RF classifiers only on training. Fit Platt calibration and choose maximum-F1 threshold only on validation. Compare all three using development AP before test; tie validation F1. Persist all copies,thresholds and decision before assessment predictions.',
        'notes':'Pinned archived Calendar row/date checks; late-edited,missing or mismatched notes unknown. No live download or outcome-based source repair.',
        'limits':'Shortlist chosen adaptively after original100test; larger historical period also examined earlier. Not independent prospective confirmation. Sparse/retrospective notes and source linkage limits remain.'})
    f=c.prepare_input(b.load_dataset_input(source));raw=pd.DataFrame(json.loads(calendar.read_text(encoding='utf-8'))['records'])
    f=f.join(available_notes(f,raw));train,val,test=make_partitions(f)
    assert (len(train),len(val),len(test))==(1506,1177,2075)
    support=[{'Partition':n,'Services':len(d),'Returns':int(d[b.TARGET].sum()),'Timely notes':int(d.notes_unknown.eq(0).sum())} for n,d in [('Training',train),('Validation',val),('Assessment',test)]]
    save(OUT/'coverage.json',support);manifest={};validation=[]
    baseline=joblib.load(baselinepath);joblib.dump(baseline,OUT/'baseline.joblib')
    with threadpool_limits(limits=2):p=b.apply_calibrator(baseline['calibrator'],baseline['pipeline'].predict_proba(val[baseline['features']])[:,1])
    validation.append({'candidate':'Original 93-input baseline',**b.score(val[b.TARGET],p,baseline['threshold'])})
    manifest['Original 93-input baseline']={'file':'baseline.joblib','sha256':sha(OUT/'baseline.joblib'),'inputs':len(baseline['features']),'threshold':baseline['threshold']}
    for i,(name,cols) in enumerate(contracts.items()):
        pipe=make_model('Random Forest',cols)
        with threadpool_limits(limits=2):
            pipe.fit(train[cols],train[b.TARGET]);rawp=pipe.predict_proba(val[cols])[:,1]
            cal,_=b.fit_calibrator(val[b.TARGET],rawp);q=b.apply_calibrator(cal,rawp);cut=b.select_threshold(val[b.TARGET],q)
        validation.append({'candidate':name,**b.score(val[b.TARGET],q,cut)})
        model={'pipeline':pipe,'features':cols,'calibrator':cal,'threshold':cut,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha(OUT/'protocol.json')}
        filename=f'rf_{i}.joblib';joblib.dump(model,OUT/filename);manifest[name]={'file':filename,'sha256':sha(OUT/filename),'inputs':len(cols),'threshold':cut,'frozen_at_utc':model['frozen_at_utc']}
    selected=max(validation,key=lambda r:(r['average_precision'],r['f1']))['candidate']
    save(OUT/'validation_results.json',validation);save(OUT/'frozen_manifest.json',{'models':manifest,'selected_using_validation_only':selected,'all_saved_before_assessment':True,'saved_at_utc':datetime.now(timezone.utc).isoformat()})
    results=[];private=[]
    for name,entry in manifest.items():
        assert sha(OUT/entry['file'])==entry['sha256'];m=joblib.load(OUT/entry['file'])
        with threadpool_limits(limits=2):p=b.apply_calibrator(m['calibrator'],m['pipeline'].predict_proba(test[m['features']])[:,1])
        met=b.score(test[b.TARGET],p,m['threshold']);tn,fp,fn,tp=confusion_matrix(test[b.TARGET],p>=m['threshold'],labels=[False,True]).ravel()
        results.append({'candidate':name,'selected_using_validation':name==selected,'inputs':len(m['features']),'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),
            **met,'cluster_95pct_intervals':bootstrap_intervals(test,p,m['threshold'])})
        pd.DataFrame({'actual':test[b.TARGET].to_numpy(),'probability':p}).to_csv(OUT/entry['file'].replace('.joblib','_assessment.csv'),index=False)
        print(name,met['precision'],met['recall'],met['f1'],flush=True)
    previous_result=json.loads((ROOT/'outputs/model_validation/20261017_larger_frozen_test/results.json').read_text())['metrics']
    assert all(np.isclose(results[0][k],previous_result[k]) for k in ['accuracy','precision','recall','f1','average_precision','brier_score'])
    assert all(sha(ROOT/p)==h for p,h in protected.items())
    save(OUT/'results.json',results);save(OUT/'verification.json',{'original_frozen_unchanged':True,'baseline_all_metrics_reproduced':True,'three_artifacts_saved_before_assessment':True,'selected_on_validation':selected,'assessment_services':2075,'positive_outcomes':184})
    report(results,support,selected)

def report(results,support,selected):
    table=[{'Model':r['candidate'],'Inputs':r['inputs'],'Chosen on validation':r['selected_using_validation'],'Accuracy %':100*r['accuracy'],
        'Precision %':100*r['precision'],'Recall %':100*r['recall'],'F1':r['f1'],'Correct alerts':r['TP'],'False alerts':r['FP'],'Missed returns':r['FN']} for r in results]
    pd.DataFrame(table).to_csv(OUT/'comparison.csv',index=False)
    payload=json.dumps(table)
    cells=[nbformat.v4.new_markdown_cell('''# Larger comparison of the two shortlisted Random Forest models
**Same 2,075 assessment services, including 184 recorded returns.**

The 28-input Random Forest and 39-input notes version use their unchanged settings. Training contains 1,506 services and validation 1,177. Property/package groups are separated and outcomes mature before subsequent partitions. Missing notes do not remove any rows.

The original93-input baseline was replayed exactly. Random Forest calibration and thresholds used validation only. All three candidate files, thresholds and the validation choice were saved before scoring the larger assessment.

These historical periods were examined earlier, and the shortlist was suggested after the smaller100-service result. This is a consistency check, not independent prospective proof. Future-test collection remains a separate frozen experiment.'''),
        nbformat.v4.new_markdown_cell('## Candidate chosen using validation\n'+selected),nbformat.v4.new_code_cell('import json\nimport pandas as pd\nimport matplotlib.pyplot as plt\ntable=pd.DataFrame(json.loads('+repr(payload)+'))\ndisplay(table.round(2))'),
        nbformat.v4.new_code_cell("x=list(range(len(table)))\nfig,ax=plt.subplots(figsize=(10,4))\nax.bar([v-.18 for v in x],table['Precision %'],.36,label='Precision',color='#2563eb')\nax.bar([v+.18 for v in x],table['Recall %'],.36,label='Recall',color='#f59e0b')\nax.set_xticks(x,['Original 93','Random Forest 28','Random Forest + notes 39']);ax.set_ylim(0,100);ax.set_ylabel('Percent');ax.set_title('Same 2,075 historical assessment services',loc='left');ax.legend();plt.tight_layout();plt.show()"),
        nbformat.v4.new_markdown_cell('## Data coverage'),nbformat.v4.new_code_cell(f'display(pd.DataFrame({support!r}))'),
        nbformat.v4.new_markdown_cell('## Interpretation limits\nPrecision is the fraction of alerts that were right; recall is the fraction of recorded returns detected. Always predicting no return has91.13% accuracy but zero recall. Compare F1, AP and Brier alongside false alerts and missed returns.\n\nCalendar notes are text mentions, not verified treatment delivery. Raw notes and customer identities are excluded from the shareable notebook. Exact thresholds, feature lists, hashes, predictions and group-bootstrap intervals are retained in the study folder. Code cells executed with the project harness; native-kernel execution was not performed.')]
    nb=nbformat.v4.new_notebook(cells=cells);execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Larger_Shortlist_Comparison.ipynb');export_html(nb,OUT/'Larger_Shortlist_Comparison.html')

if __name__=='__main__':main()
