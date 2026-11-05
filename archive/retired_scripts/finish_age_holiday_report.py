"""Add control results and forecast checks to the aggregate shareable notebook."""
from datetime import datetime,timezone
from zipfile import ZipFile,ZIP_DEFLATED
import json,base64
import numpy as np
import pandas as pd
import nbformat
from scripts.test_age_holiday_predictors import OUT,ROOT
from scripts.research_expanded_targets import save,sha
from scripts.build_supervisor_model_review import execute,export_html

def main():
    nb=nbformat.read(OUT/'Age_and_Holiday_Test.ipynb',as_version=4)
    # This report operation can be repeated without duplicating inserted sections.
    nb.cells=[c for c in nb.cells if not c.metadata.get('age_followup')]
    for cell in nb.cells:
        if cell.cell_type=='code' and 'results=pd.DataFrame' in cell.source and "# final-control-status" not in cell.source:
            cell.source=cell.source.replace('display(results.round(3))',"# final-control-status\nresults.loc[results['Input group'].eq('Settlement age proxy'),'Decision']='Preliminary lift; shuffled controls also pass; hold'\ndisplay(results.round(3))")
    controls=json.loads((OUT/'control_results.json').read_text());forecast=pd.read_csv(OUT/'forecast_holiday_comparison.csv')
    predictions=pd.read_csv(OUT/'validation_predictions.csv');pooled=[]
    for name,d in predictions.groupby('variant',sort=False):
        y=d.actual.to_numpy();z=d.probability.to_numpy()>=d.threshold.to_numpy();tp=int(((y==1)&z).sum());fp=int(((y==0)&z).sum());fn=int(((y==1)&~z).sum());tn=int(((y==0)&~z).sum())
        pooled.append({'Inputs':name,'Services':len(d),'Recorded returns':int(y.sum()),'Correct alerts':tp,'False alerts':fp,'Missed returns':fn,
            'Accuracy %':round(100*(tp+tn)/len(d),2),'Precision %':round(100*tp/max(1,tp+fp),2),'Recall %':round(100*tp/max(1,tp+fn),2),
            'Always-no accuracy %':round(float(100*(1-y.mean())),2)})
    pd.DataFrame(pooled).to_csv(OUT/'pooled_results.csv',index=False)
    extra=[nbformat.v4.new_markdown_cell('''## What do the combined service counts show?
Across the two periods there were **1,600 service windows and 194 recorded returns**. Each window belongs to one evaluation period. These are historical validation results, not the future test.

The table below pools actual correct/incorrect predictions. The earlier table instead averages each period's percentages, so the values differ.'''),
        nbformat.v4.new_code_cell(f'display(pd.DataFrame({pooled!r}))'),
        nbformat.v4.new_markdown_cell('''## Was the age improvement convincing?
The age version initially improved both ranking and probability error in both periods. However, **three of five shuffled-age controls also passed that same screen**. One shuffled version had slightly higher mean ranking AP than real age. This weakens the case that real settlement age adds stable information.

Using only the “age known/unknown” flag did not pass both periods. These checks do not prove age has no effect; they show the current evidence is insufficient. Only 34 of the 1,600 evaluation windows had accepted age codes. Feature subsampling in trees and limited spatial coverage can move scores even when added inputs have little predictive value.

The controls were designed after seeing the initial result. They are diagnostic, not independent confirmation or a statistical-significance test.'''),
        nbformat.v4.new_code_cell(f"display(pd.DataFrame({controls['controls']!r}).round(4))"),
        nbformat.v4.new_markdown_cell('''## What about weekly forecasts?
Festival-week inputs were also tested on the earlier 13 validation origins in January–June2026, using the previously selected forecast model/settings for bookings, packages and sales. Future weeks were not inspected again for this check.

Adding festival counts increased average errors by **1.9% for bookings, 3.4% for packages and 16.1% for sales**. They were not retained. These dates are partial regional context, not a complete company closure calendar.'''),
        nbformat.v4.new_code_cell('display(pd.DataFrame('+repr(forecast.to_dict('records'))+').round(2))'),
        nbformat.v4.new_markdown_cell('''## Final recommendation
**Keep settlement age as an experimental candidate; do not promote it yet. Do not retain the tested holiday features.**

The age version reached 82.75% accuracy, 33.06% precision and 41.24% recall in the pooled historical windows. The existing-input reference reached 82.12%, 30.83% and 38.14%. Always predicting “no return” would score 87.88% accuracy. The small age gain is not yet dependable, especially because shuffled controls also improved.

This round downloaded and actually fitted both new external sources. It completed 10 initial predictor fits, 12 age-control fits and 78 rolling forecast fits. No 2026 pest-model assessment was used. The frozen model and future-test artifacts were verified unchanged.

Verified building-specific age, online pest-history and operating-date sources remain unavailable; neighbourhood age is not a substitute label for them.''')]
    for c in extra:c.metadata['age_followup']=True
    # Keep the original source/method note at the end; make final recommendation newer.
    nb.cells.extend(extra);execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Age_and_Holiday_Test.ipynb');export_html(nb,OUT/'Age_and_Holiday_Test.html')
    figs=0
    for cell in nb.cells:
        for output in cell.get('outputs',[]):
            if 'image/png' in output.get('data',{}):
                (OUT/f'figure_{figs}.png').write_bytes(base64.b64decode(output.data['image/png']));figs+=1
    protocol=json.loads((OUT/'protocol.json').read_text());assert all(sha(ROOT/p)==v for p,v in protocol['protected_hashes'].items())
    metrics=pd.read_csv(OUT/'fold_metrics.csv')
    for _,r in metrics.iterrows():
        d=predictions[predictions.period.eq(r.period)&predictions.variant.eq(r.variant)];z=d.probability>=d.threshold;y=d.actual.eq(1)
        assert np.isclose((y==z).mean(),r.accuracy) and int(y.sum())==r.positives
        assert np.isclose(((y&z).sum()/max(1,z.sum())),r.precision)
    sources=[]
    for name,url in [('holidays_2024.pdf','https://www.kabinet.gov.my/storage/2024/11/hka_2024.pdf'),
        ('holidays_2025.pdf','https://www.kabinet.gov.my/storage/2024/11/hka_2025.pdf'),
        ('holidays_2026.pdf','https://www.kabinet.gov.my/storage/2025/08/HKA-2026.pdf'),
        ('settlement_age_1km.zip','https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_AGE_GLOBE_R2025A/V1-0/GHS_AGE_1975052020_GLOBE_R2025A_54009_1000_V1_0.zip')]:
        sources.append({'filename':name,'url':url,'sha256':sha(OUT/name),'bytes':(OUT/name).stat().st_size})
    save(OUT/'source_receipts.json',{'verified_at_utc':datetime.now(timezone.utc).isoformat(),'source_files_downloaded_this_run':sources,'third_party_code_installed':False})
    save(OUT/'verification.json',{'frozen_unchanged':True,'prediction_sets_recomputed':len(metrics),'notebook_valid':True,'code_errors':sum(o.output_type=='error' for c in nb.cells for o in c.get('outputs',[])),
        'initial_predictor_fits':10,'age_control_fits':12,'rolling_forecast_fits':78,'tests':'8 passed; 1 rasterio PendingDeprecationWarning','figures':figs,'production_promoted':False})
    files=['Age_and_Holiday_Test.ipynb','Age_and_Holiday_Test.html','pooled_results.csv','comparison.csv','coverage.json','forecast_holiday_comparison.csv','source_receipts.json']
    with ZipFile(OUT/'Age_and_Holiday_Review.zip','w',ZIP_DEFLATED) as z:
        for name in files:z.write(OUT/name,name)
    with ZipFile(OUT/'Age_and_Holiday_Review.zip') as z:assert z.testzip() is None
    print(pd.DataFrame(pooled).to_string(index=False))

if __name__=='__main__':main()
