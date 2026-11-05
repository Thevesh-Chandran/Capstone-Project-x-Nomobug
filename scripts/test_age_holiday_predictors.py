"""Paired predictor study using downloaded official source files.

Age is a coarse 1km settlement proxy. Publication begins June 2025, so compare
only 2025Q3/Q4. No frozen model writes or final-2026 assessment access.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,zipfile
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform
from threadpoolctl import threadpool_limits
import nbformat
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.research_callback_targets import calibration_split
from scripts.research_expanded_targets import ROOT,save,sha
from scripts.build_supervisor_model_review import execute,export_html

OUT=ROOT/'outputs/model_validation/20261018_age_holidays'
# Manually transcribed named dates from federal tables and common KL/Selangor
# state dates. A partial festival calendar: no inferred substitute/extra holidays.
DATES={2024:['01-01','01-25','02-10','02-11','03-28','04-10','04-11','05-01','05-22','06-03','06-17','07-07','08-31','09-16','10-31','12-25'],
       2025:['01-01','01-29','01-30','02-11','03-18','03-31','04-01','05-01','05-12','06-02','06-07','06-27','08-31','09-05','09-16','10-20','12-25'],
       2026:['01-01','02-01','02-17','02-18','03-07','03-21','03-22','05-01','05-27','05-31','06-01','06-17','08-25','08-31','09-16','11-08','12-25']}
HOLIDAYS=['festival_day','festival_days_previous_7','festival_days_next_7','days_to_next_festival_capped30']
WEEKDAY=['weekday_sin','weekday_cos']
AGE=['settlement_age_code','settlement_age_unknown']

def holiday_features(dates):
    events=pd.DatetimeIndex(sorted(pd.Timestamp(f'{y}-{day}') for y,days in DATES.items() for day in days))
    rows=[]
    for value in dates:
        date=pd.Timestamp(value).normalize();delta=(events-date).days.to_numpy()
        # Unknown years must stay unknown, rather than becoming zero holidays.
        known=date.year in DATES
        rows.append({'festival_day':int((delta==0).any()) if known else np.nan,
            'festival_days_previous_7':int(((delta>=-7)&(delta<0)).sum()) if known else np.nan,
            'festival_days_next_7':int(((delta>0)&(delta<=7)).sum()) if known else np.nan,
            'days_to_next_festival_capped30':float(min(30,delta[delta>=0].min())) if known and (delta>=0).any() else np.nan,
            'weekday_sin':np.sin(date.dayofweek*2*np.pi/7),'weekday_cos':np.cos(date.dayofweek*2*np.pi/7)})
    return pd.DataFrame(rows,index=dates.index)

def age_at_locations(locations,path):
    result={};coverage={'requested_addresses':len(locations),'spatially_stable_nonzero':0,'crosses_age_boundary':0,'non_built_or_nodata':0}
    with rasterio.open(path) as src:
        for row in locations.itertuples():
            # Quarter-cell offset checks roughly bound the accepted 250m location
            # uncertainty. No claim of exact-footprint or complete-circle certainty.
            x,y=transform('EPSG:4326',src.crs,[row.longitude],[row.latitude]);x=x[0];y=y[0]
            points=[(x+dx,y+dy) for dx,dy in [(0,0),(-250,0),(250,0),(0,-250),(0,250),(-250,-250),(-250,250),(250,-250),(250,250)]]
            vals=[int(v[0]) for v in src.sample(points)]
            if any(v<1 or v>10 for v in vals):coverage['non_built_or_nodata']+=1;continue
            if len(set(vals))!=1:coverage['crosses_age_boundary']+=1;continue
            result[row.address_hash]=vals[0];coverage['spatially_stable_nonzero']+=1
    return result,coverage

def main():
    assert not (OUT/'protocol.json').exists(),'Preserve existing declared experiment'
    source=ROOT/'outputs/cp2-v2/source_refresh_20260927/refreshed/dataset_input.json'
    loc=ROOT/'outputs/model_validation/20261017_interservice_weather_v2/address_locations_private.json'
    raster=next(OUT.glob('*.tif'));bundle=ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json'
    protected={str(p.relative_to(ROOT)):sha(p) for p in bundle.parent.iterdir() if p.is_file()}
    folds=[v for v in b.DEVELOPMENT_FOLDS if v[1]>='2025-07-01']
    save(OUT/'protocol.json',{'declared_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),
        'sources':{str(p.relative_to(ROOT)):sha(p) for p in [source,loc,raster,*OUT.glob('holidays_*.pdf')]},'protected_hashes':protected,
        'target':'Recorded pest-related return within 30 days after a paid service','model':'Existing ExtraTrees settings; 93 baseline inputs',
        'folds':folds,'feature_groups':{'Festival dates':HOLIDAYS,'Day of week':WEEKDAY,'Settlement age proxy':AGE},
        'selection':'Paired comparison; identical chronological/property-purged fitting and calibration. Keep addition only if AP rises and Brier falls in both periods; precision/recall also reported. No 2026 assessment.',
        'age_scope':'GHS-AGE 1975-2020, released June26 2025, 1km Mollweide. Retrospectively reconstruct earlier training features using a source available before evaluation starts. Location uncertainty <=250m; nine offset samples must agree on valid built-stock code.',
        'holiday_scope':'Transcribed nominal federal/common KL-Selangor festival dates. Partial regional context, not exact state/company closure calendar. No substitute days or one-off gazettes inferred. Dates marked subject to change; as-issued revisions incomplete.',
        'limits':'Adaptive historical study on previously inspected data. Coarse settlement age is not customer-building age; geocodes reconstructed later. Two periods cannot establish reliability or significance.'})
    f=c.prepare_input(b.load_dataset_input(source));f=f[f.anchor_date<'2026-01-01'].copy()
    locations=pd.DataFrame(json.loads(loc.read_text()));precise=set(f.loc[f.location_uncertainty_radius_m.le(250),'address_hash'])
    locations=locations[locations.address_hash.isin(precise)]
    codes,spatial=age_at_locations(locations,raster)
    f=f.join(holiday_features(f.anchor_date));f['settlement_age_code']=f.address_hash.map(codes).where(f.location_uncertainty_radius_m.le(250))
    f['settlement_age_unknown']=f.settlement_age_code.isna().astype(int)
    coverage={'development_source_rows':len(f),'precision_eligible_addresses':len(precise),'spatial':spatial,
        'services_with_age_proxy':int(f.settlement_age_code.notna().sum()),'age_proxy_unknown':int(f.settlement_age_code.isna().sum()),
        'festival_dates_per_year':{k:len(v) for k,v in DATES.items()},'uncovered_year_rows':int(f.festival_day.isna().sum())}
    save(OUT/'coverage.json',coverage);save(OUT/'festival_dates_transcribed.json',DATES)
    pd.DataFrame([{'address_hash':key,'settlement_age_code':value} for key,value in codes.items()]).to_csv(OUT/'age_matches_private.csv',index=False)
    features=json.loads(bundle.read_text())['models']['challenger_all_history']['features']
    variants={'Existing inputs':[],'Festival dates':HOLIDAYS,'Day of week':WEEKDAY,'Settlement age proxy':AGE,'All additions':HOLIDAYS+WEEKDAY+AGE}
    rows=[];prediction_sets=[]
    for fold,start,end in folds:
        train,test,audit=b.purged_split(f,start,end);fit,cal,_=calibration_split(train)
        for variant,extra in variants.items():
            active=[x for x in extra if fit[x].nunique(dropna=True)>1];cols=features+active
            pipe=c.make_pipeline('et10_leaf5',[x for x in cols if x not in b.CATEGORICAL])
            with threadpool_limits(limits=2):
                pipe.fit(fit[cols],fit[b.TARGET],classifier__sample_weight=c.training_weights(fit,'standard'))
                calibrator,_=b.fit_calibrator(cal[b.TARGET],pipe.predict_proba(cal[cols])[:,1])
                threshold=b.select_threshold(cal[b.TARGET],b.apply_calibrator(calibrator,pipe.predict_proba(cal[cols])[:,1]))
                p=b.apply_calibrator(calibrator,pipe.predict_proba(test[cols])[:,1]);metrics=b.score(test[b.TARGET],p,threshold)
            rows.append({'period':fold,'variant':variant,'inputs':len(cols),'fit_rows':len(fit),'calibration_rows':len(cal),'test_rows':len(test),'positive_returns':int(test[b.TARGET].sum()),'known_age_test_rows':int(test.settlement_age_code.notna().sum()),'threshold':threshold,**metrics})
            for y,v in zip(test[b.TARGET],p):prediction_sets.append({'period':fold,'variant':variant,'actual':int(y),'probability':float(v),'threshold':threshold})
            pd.DataFrame(rows).to_csv(OUT/'fold_metrics.csv',index=False);print(fold,variant,round(metrics['precision'],3),round(metrics['recall'],3),flush=True)
    df=pd.DataFrame(rows);base=df[df.variant.eq('Existing inputs')].set_index('period');summary=[]
    for name,part in df.groupby('variant',sort=False):
        part=part.set_index('period');wins=(part.average_precision>base.average_precision)&(part.brier_score<base.brier_score)
        summary.append({'Input group':name,'Mean precision':float(part.precision.mean()),'Mean recall':float(part.recall.mean()),'Mean F1':float(part.f1.mean()),
            'Mean AP':float(part.average_precision.mean()),'Mean Brier':float(part.brier_score.mean()),'Periods improved on both':int(wins.sum()),
            'Decision':'Reference' if name=='Existing inputs' else ('Candidate needs further validation' if wins.all() else 'Do not adopt')})
    pd.DataFrame(prediction_sets).to_csv(OUT/'validation_predictions.csv',index=False);pd.DataFrame(summary).to_csv(OUT/'comparison.csv',index=False)
    assert all(sha(ROOT/p)==v for p,v in protected.items())
    save(OUT/'acceptance.json',{'fits':len(rows),'frozen_unchanged':True,'no_2026_assessment':True,'coverage':coverage,'summary':summary})
    report(summary,coverage)

def report(summary,coverage):
    text='''# Did settlement age and holidays improve the model?
**18 October 2026 — two paired historical validation periods.**

## What was actually added?
**Settlement age:** downloaded Copernicus GHS-AGE, a 1km map estimating when half of the grid cell's 2020 built-up surface had been reached. It describes older/newer surrounding development. It does not verify the age of an individual building.

**Festival dates:** downloaded and transcribed the official 2024–2026 calendars. Tested whether service falls on a nominal holiday/festival date, nearby holiday counts and days to the next date. The partial calendar uses federal/common KL–Selangor dates; replacement days, extra gazettes and exact business closures are not inferred.

**Day of week:** tested separately, so any calendar benefit cannot automatically be attributed to holidays.

## How were they tested?
The existing 30-day return question and ExtraTrees settings were used as the reference. Each addition was trained separately and together. Training, probability calibration and thresholds used earlier records, with property/package separation. July–September and October–December 2025 were the two evaluation periods. This is adaptive historical research; these periods have been inspected before.

The settlement source was released in June 2025, so earlier prediction periods were not evaluated. Earlier training features were reconstructed using the 2020 settlement map available before these evaluation periods. Current geocodes and source revisions remain retrospective limitations.

## Results
Precision means: when the model predicts a return, how often a return was recorded. Recall means: how many recorded returns were found. AP measures ranking; Brier measures probability error (lower is better). Table values are period averages, not pooled service percentages.
'''
    cells=[nbformat.v4.new_markdown_cell(text),nbformat.v4.new_code_cell('import pandas as pd\nimport matplotlib.pyplot as plt\n'+f"results=pd.DataFrame({summary!r})\ndisplay(results.round(3))"),
        nbformat.v4.new_code_cell("fig,ax=plt.subplots(figsize=(9,4))\nax.barh(results['Input group'],results['Mean AP'],color=['#334155','#2563eb','#f59e0b','#7c3aed','#0891b2'])\nax.set_xlabel('Average precision — higher is better')\nax.set_title('Ranking quality in two 2025 periods',loc='left')\nax.invert_yaxis();plt.tight_layout();plt.show()"),
        nbformat.v4.new_markdown_cell('## Coverage\n'+f"Of {coverage['development_source_rows']} earlier services, **{coverage['services_with_age_proxy']}** had an accepted settlement-age proxy. The rest remain unknown. Only recorded location uncertainty ≤250m and nine agreeing raster samples were accepted. The raster is 1km, so this remains approximate neighbourhood context.\n\nSparse coverage limits the ability to detect a useful effect. Missing ages were not invented. No verified online building-specific pest history was obtained."),
        nbformat.v4.new_markdown_cell('## Decision\nAn input must improve both AP and Brier in both periods to be considered promising. Even a pass would need further confirmation. No frozen model or production predictions were altered. The 2026 assessment was not used here.\n\n[Copernicus GHS-AGE source](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_AGE_GLOBE_R2025A/V1-0/) · [Official holiday calendars](https://www.kabinet.gov.my/hari-kelepasan-am/)\n\nNotebook cells executed sequentially with the project harness; no separate native-kernel run. Model retraining needs the private project sources. The notebook embeds aggregate results only.')]
    nb=nbformat.v4.new_notebook(cells=cells);execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Age_and_Holiday_Test.ipynb');export_html(nb,OUT/'Age_and_Holiday_Test.html')

if __name__=='__main__':main()
