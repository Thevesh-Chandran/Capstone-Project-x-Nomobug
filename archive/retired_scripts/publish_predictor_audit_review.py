"""Add completed removal evidence and unresolved issues to the supervisor guide."""
import hashlib,json,zipfile
import pandas as pd
import nbformat
from scripts.audit_predictor_value import ROOT,OUT
from scripts.simplify_supervisor_review import OUT as REVIEW
from scripts.build_supervisor_model_review import execute,export_html

def main():
    done=json.loads((OUT/'individual_removal_acceptance.json').read_text())
    assert done['fits']==279 and done['variables']==93 and done['frozen_unchanged']
    group=pd.read_csv(OUT/'group_decisions.csv');individual=pd.read_csv(OUT/'individual_removal_decisions.csv')
    folds=pd.read_csv(OUT/'individual_removal_fold_metrics.csv')
    assert len(folds)==279 and not folds.duplicated(['fold','removed']).any()
    assert len(group)==7 and len(individual)==93
    for filename in ['group_decisions.csv','individual_removal_decisions.csv','individual_predictor_screen.csv','protocol.json','individual_removal_protocol.json','acceptance.json','individual_removal_acceptance.json','combined_candidate_metrics.csv','combined_candidate_protocol.json']:
        (REVIEW/'data'/filename).write_bytes((OUT/filename).read_bytes())
    note='''## Were the variables tested, or simply added?
Now each of the 93 inputs has been tested by retraining without it in three earlier periods: **279 individual removal fits**, plus **21 whole-group fits** and **279 variable-shuffling checks**. The three validation periods contain 2,478 service windows and 229 recorded returns. Training and calibration use earlier, property/package-purged records. The final 100-service holdout was not used in these new tests.

For each variable below, **AP change after removal** measures the change in ranking quality (positive favours removal). **Brier change after removal** measures the change in probability error (negative favours removal). These are score differences, not percentage-point changes in accuracy. Decision thresholds were selected on earlier calibration data only.

A removal is a candidate only if both measures improve in all three periods. Mixed evidence means do not automatically remove it. Even a consistent removal candidate needs confirmation: we have already explored this historical dataset extensively, and testing 93 removals can produce chance winners. Removing several together also needs its own validation; individual gains do not add up.

No frozen weights or future predictions were changed. This is historical development evidence, not a new independent performance claim.
'''
    # Recreate the basic guide first so this publication is idempotent.
    from scripts.simplify_supervisor_review import main as reset_guide
    reset_guide()
    nb=nbformat.read(REVIEW/'START_HERE_Variables.ipynb',as_version=4)
    nb.cells.insert(1,nbformat.v4.new_markdown_cell(note))
    nb.cells.insert(2,nbformat.v4.new_code_cell("from pathlib import Path\nimport pandas as pd\nBASE=Path.cwd()\nif not (BASE/'data/group_decisions.csv').exists():\n    BASE=BASE/'outputs/supervisor_model_review/20261017'\ngroups=pd.read_csv(BASE/'data/group_decisions.csv')\ndisplay(groups[['variant','AP_change_vs_full','Brier_change_vs_full','folds_improved_both','decision']].rename(columns={'variant':'Group removal','AP_change_vs_full':'AP change','Brier_change_vs_full':'Brier change','folds_improved_both':'Periods improved both','decision':'Decision'}).round(4))"))
    original=next(cell for cell in nb.cells if cell.cell_type=='code' and "variables=pd.read_csv" in cell.source)
    original.source=original.source.replace("assert len(variables)==93", "decisions=pd.read_csv(BASE/'data/individual_removal_decisions.csv')\nvariables=variables.merge(decisions.drop(columns='Variable'),on='Technical field',validate='one_to_one')\nvariables['Removal test']=variables.apply(lambda r:f\"{r['Decision']}; AP change {r['Mean AP change after removal']:+.4f}; Brier change {r['Mean Brier change after removal']:+.4f}; {int(r['Folds improved both'])}/3 periods improved both.\",axis=1)\nvariables=variables.drop(columns=['Mean AP change after removal','Mean Brier change after removal','Folds improved both','Decision'])\nassert len(variables)==93")
    nb.cells[0].source=nb.cells[0].source.replace('**Contribution to model performance:** also not established for each variable by this table. That requires a separate validation comparison with and without the variable; correlations cannot substitute for it.','**Contribution to model performance:** now investigated separately through the removal tests below. Correlations alone cannot establish it.')
    nb.cells.append(nbformat.v4.new_markdown_cell('''## Still unresolved
1. **New data:** current food-outlet context has now been collected for all 1,127 archived environmental locations (781 with mapped food within 500 m; one capped result). Historical opening/closing dates, precise customer alignment and business deduplication remain unverified, so it is not a trained input. A 100-location building check found no construction-date tags in returned records; 40 responses were capped and none establishes building identity or age. Official facility sources have been identified but verified coordinates, operating dates and inventory completeness remain unresolved. No verified general building pest-history registry was found.
2. **Simplified replacement:** four individual removal candidates were found. Removing all four together produced an 89-input model with slightly lower probability error in all three periods, but worse ranking quality in two. It is not a consistently better replacement. Independent confirmation and any further refinement remain; the frozen experiment is unchanged.
3. **Label verification:** current labels represent recorded corrective returns. A positive/negative sample still needs independent source review; missing records cannot be interpreted as verified absence of pests.
4. **Future evaluation:** the recovery cohort still needs complete timely predictions and mature outcomes. The planned review is 30 November. Historical missed windows cannot be backfilled.
5. **Owner facts:** Owner confirmed Client M is the same client and the October visit is simply her second service, with no restart. Internal duplicate-session/source-link reconciliation remains; do not ask the owner to confirm an inferred renewal. Owner confirmed Hotel client H was a free service, so its missing paid Sales match is explained and should not be chased. These facts are recorded separately from the original recovery audit; no historical prediction receipt was rewritten.
6. **Location coverage:** last verified map release had 226 unmapped purchases out of 886; daily batches and ambiguous-address review remain. This is a dated release count, not a fresh live check.
7. **AI assistant:** open-ended Ollama response time and wider answer reliability remain limited; fast verified answers cover only supported questions.
8. **Final operations checks:** verify the final amended daily image on a scheduled source-to-Gold run, current spending, failure/recovery evidence and final submission records. Dashboard work remains with the owner.

### Sources for proposed inputs
[Geoapify Places API](https://apidocs.geoapify.com/docs/places/) provides mapped catering locations. [OpenStreetMap building attributes](https://wiki.openstreetmap.org/wiki/Building_attributes) describe construction-date tags; a business opening date is not a building construction date. [OpenStreetMap wastewater facilities](https://wiki.openstreetmap.org/wiki/Tag%3Aman_made%3Dwastewater_plant) distinguish sewage treatment from drinking-water facilities. These documents establish possible sources, not verified coverage or predictive benefit.
'''))
    execute(nb);nbformat.validate(nb);nbformat.write(nb,REVIEW/'START_HERE_Variables.ipynb');export_html(nb,REVIEW/'START_HERE_Variables.html')
    p=REVIEW/'START_HERE_Variables.html';s=p.read_text(encoding='utf-8').replace('<body>','<body><label>Find a variable <input id="find" placeholder="Try rain, age, cockroach…" style="padding:12px;width:300px"></label>')
    s+='<script>document.getElementById("find").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script>'
    p.write_text(s,encoding='utf-8')
    (OUT/'UNRESOLVED_ISSUES.md').write_text(nb.cells[-1].source,encoding='utf-8')
    (REVIEW/'README.txt').write_text('Start with START_HERE_Variables.html. All 93 inputs have plain-English definitions and individual removal results.\nNotebook: START_HERE_Variables.ipynb. Three code cells executed with a sequential Python harness; native Jupyter kernel unavailable.\nHistorical development audit only: no frozen-model changes or new independent accuracy claims.\nHTML browser preview unavailable under current file-URL policy.\nTechnical source data and hashes are in data/. No private customer rows included.\n',encoding='utf-8')
    (REVIEW/'data/manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((REVIEW/'data').iterdir()) if p.name!='manifest.json'},indent=2))
    with zipfile.ZipFile(REVIEW/'CP2_Supervisor_Review.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in [*REVIEW.glob('*.html'),*REVIEW.glob('*.ipynb'),REVIEW/'README.txt',*sorted((REVIEW/'data').glob('*'))]:z.write(p,p.relative_to(REVIEW))
    print(individual.Decision.value_counts().to_string())
    print('Verified complete removal matrices, executed updated notebook, rebuilt supervisor ZIP.')

if __name__=='__main__':main()

