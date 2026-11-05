"""Render saved research and diagnostic baselines without retuning selections."""
from __future__ import annotations
import base64
import contextlib
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import nbformat
from scripts.research_additional_models import ROOT,BASELINES,origins,predict,metrics,save,digest

FOLDER=ROOT/'outputs/additional_model_research/20261014'


def diagnostics():
    frame=pd.read_csv(FOLDER/'weekly_targets.csv',index_col=0,parse_dates=True)
    results=json.loads((FOLDER/'results.json').read_text());records=[]
    for target in frame:
        series=frame[target].dropna()
        for horizon in (1,4):
            for name in BASELINES:
                rows=[]
                for origin in origins('2026-07-20','2026-10-05',horizon):
                    p=predict(series,origin,horizon,name,'all')
                    actual=float(series[(series.index>=origin)&(series.index<origin+pd.Timedelta(weeks=horizon))].sum())
                    rows.append({'actual':actual,'prediction':p})
                records.append({'target':target,'horizon':horizon,'model':name,**metrics(rows)})
    pd.DataFrame(records).to_csv(FOLDER/'all_baseline_sensitivity.csv',index=False)
    # This is explicitly post-test diagnosis, never a new holdout-selected winner.
    save(FOLDER/'diagnostic_status.json',{'status':'Post-holdout sensitivity only; original development selections and holdout results preserved',
        'reason':'Check whether an advanced model improvement depends on a weak development-selected baseline'})
    return frame,results,pd.DataFrame(records)


def figures(frame,results,baseline):
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
    predictions=pd.read_csv(FOLDER/'predictions.csv',parse_dates=['origin'])
    chosen=predictions[(predictions.target=='weekly_bookings')&(predictions.horizon==1)&(predictions.phase=='holdout')&(predictions.model=='hist_gradient_boosting')]
    series=frame.weekly_bookings.dropna();moving=[predict(series,d,1,'mean_4','all') for d in chosen.origin]
    fig,axes=plt.subplots(2,1,figsize=(11,7),constrained_layout=True)
    axes[0].plot(series.index,series,color='#528fb7',linewidth=1.5)
    axes[0].axvspan(pd.Timestamp('2026-07-20'),pd.Timestamp('2026-10-12'),color='#d6eaf6',alpha=.5)
    axes[0].set(title='Recorded weekly bookings: changing history and later test block',ylabel='Bookings / week')
    axes[0].grid(axis='y',alpha=.2)
    axes[1].plot(chosen.origin,chosen.actual,'o-',label='Actual bookings',color='#25384f')
    axes[1].plot(chosen.origin,chosen.prediction,'s--',label='Development-selected boosting',color='#8b7ec8')
    axes[1].plot(chosen.origin,moving,'^--',label='Previous four-week average (diagnostic)',color='#d19b43')
    axes[1].set(title='One-week forecast: advanced model versus a strong simple alternative',ylabel='Bookings / week',xlabel='Forecast week starting Monday')
    axes[1].legend(fontsize=9);axes[1].grid(axis='y',alpha=.2)
    fig.savefig(FOLDER/'booking_forecast_evidence.png',dpi=160);plt.close(fig)
    b=baseline[(baseline.target=='weekly_bookings')&(baseline.horizon==1)]
    labels=['Last week','Four-week average','Eight-week average','Same week last year','Selected boosting']
    values=list(b.mae)+[results['weekly_bookings_h1']['holdout']['mae']]
    fig,ax=plt.subplots(figsize=(9,4),constrained_layout=True)
    ax.barh(labels,values,color=['#b6cad9','#d19b43','#b6cad9','#b6cad9','#8b7ec8'])
    for i,v in enumerate(values):ax.text(v+.35,i,f'{v:.2f}',va='center')
    ax.set(xlabel='Mean absolute error (bookings)',title='Lower is better: 12 later test weeks',xlim=(0,27));ax.invert_yaxis()
    fig.savefig(FOLDER/'booking_baseline_comparison.png',dpi=160);plt.close(fig)
    repeat=json.loads((FOLDER/'repeat90_results.json').read_text())['holdout']
    fig,ax=plt.subplots(figsize=(8,4),constrained_layout=True)
    ax.bar(['Model review list','Random selection\n(expected)'],[repeat['cases_in_review_list'],repeat['random_expected_cases']],color=['#528fb7','#b6cad9'])
    ax.set(ylabel='Actual repeat buyers found',title='Review 112 of 557 customers: 19 actual repeat buyers',ylim=(0,20))
    for i,v in enumerate([repeat['cases_in_review_list'],repeat['random_expected_cases']]):ax.text(i,v+.4,f'{v:.1f}' if i else str(v),ha='center')
    ax.text(.5,18,'Model list also contains 99 non-repeat buyers',ha='center',fontsize=10)
    fig.savefig(FOLDER/'repeat_purchase_evidence.png',dpi=160);plt.close(fig)


def report(results,baseline):
    repeat=json.loads((FOLDER/'repeat90_results.json').read_text());source=json.loads((FOLDER/'source_receipt.json').read_text())
    predictions=pd.read_csv(FOLDER/'predictions.csv');count=len(predictions[predictions.phase=='development'][['target','horizon','model','window']].drop_duplicates())
    lines=['# Additional predictive models — research completed 15 October 2026','',
        'Recommendation: keep the existing pest-return v5 model unchanged. A simple weekly booking forecast and an experimental 90-day repeat-purchase ranking are the most useful additions to investigate. No new model is cleared for dependable operational use.','',
        f'Tested {count} complete forecasting configurations across three targets, two horizons and three history windows, plus six repeat-purchase classifiers. The original model and October protocol hashes were unchanged.','',
        '## Forecast comparison','',
        '| Target / horizon | Development-selected method | Test MAE | Selected baseline MAE | Error reduction |',
        '|---|---|---:|---:|---:|']
    for key,r in results.items():
        lines.append(f"| {key} | {r['selected']['model']} / {r['selected']['window']} | {r['holdout']['mae']:.2f} | {r['baseline_holdout']['mae']:.2f} | {100*r['holdout_mae_improvement']:.1f}% |")
    lines += ['', 'MAE is mean absolute error: bookings/packages in counts, sales in RM. It is not classification accuracy. Four-week targets are the sum of the next four weeks; their nine test origins overlap and are not independent.', '',
        '### The baseline check changes the booking recommendation','',
        'Boosting reduced one-week booking error from 23.00 to 11.56 against the development-selected same-week-last-year baseline, winning nine of twelve weeks. However, a post-test sensitivity check found that the four-week moving average had lower error: **9.31 bookings**, versus **11.56** for boosting. The advanced model is about 24.2% worse than this alternative. Do not advertise the 49.7% gain as superiority over simple forecasting.', '',
        'The moving-average diagnostic had WAPE 13.5%, versus 16.8% for boosting. This does not mean “86.5% accuracy.” The simple method was identified after viewing this test block, so it needs a new forward test; it is not a newly confirmed winner on untouched data.', '',
        'The research gate passed for boosting only relative to the preselected baseline. That limited pass is insufficient for promotion after the stronger baseline and source-quality checks. None of the other five target/horizon experiments met the original improvement gate.', '',
        'The illustrative 90% development-residual interval for boosting covered 12/12 later weeks but averaged 68.6 bookings wide; broad intervals and only eight calibration origins limit planning precision. Four-week booking coverage was only 4/9; it must not be advertised as a calibrated 90% interval.', '',
        '## Repeat-purchase prediction','',
        'Question: after a customer’s first **recorded** paid programme, will they buy a different programme within 90 days? An upsell within the same reviewed programme is not a repeat purchase. This differs from the current pest-return model.', '',
        f"Development: {repeat['cohorts']['development']} customers, 8 repeat buyers. Final training: {repeat['cohorts']['final_training']} mature customer histories. Later test: **557 customers, 19 repeat buyers**. Development-selected histogram gradient boosting found **13/19 (68.4%)** repeat buyers in a list of **112 customers**; **99 did not repurchase** within the window. Random selection would find about **3.82** buyers at the same review capacity. Ranking lift is **3.40×**; exploratory 90% customer-bootstrap interval **2.49–4.30×**.", '',
        'Average precision was 0.0939 against 0.0341 prevalence; ROC AUC 0.7613. The list precision was only 11.6%. These metrics describe ranking, not calibrated purchase probabilities. Selection had only eight development positives; testing had nineteen. The predeclared twenty-positive minimum failed. Do not relax it after seeing results.', '',
        'Potential use: prioritise human follow-up, with experimental status and false-alert counts. Do not send automatic marketing messages, promise purchases or label customers as lost. Prospective validation and probability calibration remain required.', '',
        '## Data and leakage audit','',
        f"Immutable release: `{source['release']}`. Three bounded BigQuery reads each used a dry run and 100 MiB cap; total successful processed bytes: {sum(r['bytes_processed'] or 0 for r in source['queries']):,}.", '',
        '- Booking series: 157 complete reconstructed weeks, 7,909 records after excluding the left-censored first week and the current partial week. Weekly year groupings can include dates from an adjacent calendar year.',
        '- Sales/package series: 135 complete weeks. Five undated sales were excluded. Nineteen included sales have missing amounts (nine in 2024, six in 2025, four in 2026); the monetary target sums known recorded amounts and does not estimate those missing values. There are 405 inferred Sales years plus five unresolved dates.',
        '- Zero weeks mean no included records in this release, not proof that collection was complete. Changes in recording or business size can create artificial trends.',
        '- Current Calendar edits/cancellation state reconstruct historical labels. 546 Calendar rows dated in 2026 were updated after their anchor-day midnight; this is a limitation, not proof that each update was after service or improper. Historical as-of labels/features cannot be fully reconstructed from this export.',
        '- Training uses only prior weeks; direct four-week training targets end before the forecast origin. No future weather or already-booked-future totals are used. Development ends before the final July–October block; model/window choice is frozen before its test scores.',
        '- Repeat training labels mature before evaluation starts. Each customer appears once. Only initial-day features are used; later upgrades, final balances and appointment counts are excluded. Four profiles with undated purchases, 130 uncertain identities, 164 immature profiles and eight without an observed dated purchase were excluded. Current matching is retrospective.',
        '- Neither the booking labels nor customer labels establish completed treatments, settled cash, profit, or genuine satisfaction. Historical evaluation is not an already-logged prospective forecast.', '',
        '## Methods and research sources','',
        'Forecast candidates: last observation, recent four/eight-week mean, annual seasonal naive, simple exponential smoothing, damped Holt, Ridge, Poisson, random forest, Extra Trees, histogram gradient boosting (squared and count losses), CatBoost. All/52-week/2026-only histories were compared. Money targets did not use Poisson. Forty-eight expected seasonal-baseline fits were unavailable because the 2026-only window has fewer than 52 weeks.', '',
        'ARIMA/ETS are valid research directions, but statsmodels was not installed and no new dependency was added. SES and damped Holt were implemented with training-only parameter fitting. Prophet, deep networks and fine district models were not run: the series contain only 135–157 weekly observations, changing recording regimes and limited repeated annual cycles. Their suitability is unproven, not ruled out universally.', '',
        'Cancellation prediction needs reliable historical change/replacement linkage and as-of snapshots; a current CANCELLED title is insufficient. Payment-lateness prediction needs actual payment dates/instalment allocations; reminders and green formatting are not such labels. Enquiry conversion needs validated enquiry-to-sale links and a mature conversion horizon. Those tasks were assessed and withheld rather than given manufactured targets.', '',
        '- [Forecasting: Principles and Practice — benchmarks, time-ordered validation, errors and intervals](https://otexts.com/fpp3/toolbox.html)',
        '- [scikit-learn — lagged features and time-series forecasting](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html)',
        '- [scikit-learn — average precision](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)',
        '- [CatBoost — regression API](https://catboost.ai/docs/en/concepts/python-reference_catboostregressor)',
        '- [statsmodels — SARIMAX](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html)', '',
        '## Additions and remaining work','',
        'Prepared reproducible protocols, scripts, source receipts, per-origin predictions, selected-model records, diagnostics, figures and a companion notebook. No current model, cloud schedule, live dashboard, OAuth permission or source record was changed.', '',
        'Recommended next additions are a clearly experimental weekly booking forecast (simple moving-average baseline shown alongside any challenger) and a repeat-purchase prioritisation pilot. Log new forecasts/rankings before outcomes and assess them against frozen baselines. Weekly booking outcomes mature weekly; repeat-purchase labels require 90 days, so a new repeat test started now cannot fully mature by 30 November. A November submission can report this historical study honestly, not a completed 90-day future test.', '',
        'Validation: 18 relevant tests passed, including later-outcome invariance, four-week time boundaries, linked-upsell labels, unknown/immature exclusions and existing v5 entrypoint guards. No full dbt run was needed because no warehouse transformation changed.', '',
        'Artifacts: `results.json`, `repeat90_results.json`, `predictions.csv`, `development_leaderboard.csv`, `all_baseline_sensitivity.csv`, `source_receipt.json`, `run_manifest.json`, `protected_artifact_check.json`. See `research_companion.ipynb` for an executed reading companion.']
    text='\n'.join(lines)+'\n'
    (FOLDER/'RESEARCH_REPORT.md').write_text(text,encoding='utf-8')
    (ROOT/'planning/CP2_ADDITIONAL_MODEL_RESEARCH_20261015.md').write_text(text,encoding='utf-8')


def notebook():
    # Execute each authored code cell in a shared Python namespace, capture outputs,
    # then validate nbformat. No notebook server or missing nbclient dependency needed.
    cells=[nbformat.v4.new_markdown_cell('# Additional model research\n\nKeep pest-return v5 unchanged. Booking moving averages and a repeat-purchase ranking are candidates, not production-validated models. This notebook reads saved immutable-release research; it does not query sources or retrain.'),
        nbformat.v4.new_code_cell("from pathlib import Path\nimport json\nimport pandas as pd\nimport matplotlib.pyplot as plt\ndef show_figure(path):\n    fig, ax = plt.subplots(figsize=(11,7))\n    ax.imshow(plt.imread(path))\n    ax.axis('off')\n    plt.show()\nfolder=Path("+repr(str(FOLDER))+ ")\nresults=json.loads((folder/'results.json').read_text())\nrepeat=json.loads((folder/'repeat90_results.json').read_text())\nprint('Source:', json.loads((folder/'source_receipt.json').read_text())['release'])"),
        nbformat.v4.new_markdown_cell('## Forecast results\nSelections used eight May–June origins. Later rolling tests used twelve one-week or nine overlapping four-week origins. Lower MAE is better; units differ by target.'),
        nbformat.v4.new_code_cell("summary=pd.DataFrame([{'task':k,'method':v['selected']['model'],'MAE':v['holdout']['mae'],'baseline_MAE':v['baseline_holdout']['mae'],'relative_gain':v['holdout_mae_improvement']} for k,v in results.items()])\nprint(summary.to_string(index=False))\nshow_figure(folder/'booking_forecast_evidence.png')"),
        nbformat.v4.new_markdown_cell('## Baseline sensitivity\nPost-test diagnostic: the four-week moving average is stronger than the development-selected seasonal baseline. It cannot be promoted as a newly confirmed winner after inspecting this same test.'),
        nbformat.v4.new_code_cell("print(pd.read_csv(folder/'all_baseline_sensitivity.csv').query(\"target=='weekly_bookings' and horizon==1\") [['model','mae','wape']].to_string(index=False))\nshow_figure(folder/'booking_baseline_comparison.png')"),
        nbformat.v4.new_markdown_cell('## Repeat-purchase results\nOne first-recorded programme per confidently matched customer; different-programme purchase within 90 days. Eight development and nineteen test positives limit reliability. There are 99 false alerts in the 112-customer review list.'),
        nbformat.v4.new_code_cell("print(json.dumps(repeat['holdout'],indent=2))\nshow_figure(folder/'repeat_purchase_evidence.png')"),
        nbformat.v4.new_markdown_cell('## Limits and preservation\nCurrent corrected records are not historical as-of snapshots. Missing sale values and inferred years limit sales forecasts. Future booking evidence matures weekly; a new 90-day repeat-purchase future test cannot finish by 30 November. Sources and methods are listed in RESEARCH_REPORT.md.'),
        nbformat.v4.new_code_cell("print(json.dumps(json.loads((folder/'protected_artifact_check.json').read_text()),indent=2))")]
    nb=nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
    ns={}
    for index,cell in enumerate(nb.cells):
        if cell.cell_type!='code':continue
        outputs=[];stdout=io.StringIO()
        def capture_display(obj):
            if hasattr(obj,'data') and isinstance(obj.data,bytes):
                outputs.append(nbformat.v4.new_output('display_data',data={'image/png':base64.b64encode(obj.data).decode(),'text/plain':'Research evidence figure'}))
            else:outputs.append(nbformat.v4.new_output('display_data',data={'text/plain':str(obj)}))
        source=cell.source
        ns['display']=capture_display
        with contextlib.redirect_stdout(stdout):exec(compile(source,f'<cell {index}>','exec'),ns)
        for number in plt.get_fignums():
            image=io.BytesIO();plt.figure(number).savefig(image,format='png',bbox_inches='tight')
            outputs.append(nbformat.v4.new_output('display_data',data={'image/png':base64.b64encode(image.getvalue()).decode(),'text/plain':'Research evidence figure'}))
        plt.close('all')
        if stdout.getvalue():outputs.insert(0,nbformat.v4.new_output('stream',name='stdout',text=stdout.getvalue()))
        cell.outputs=outputs;cell.execution_count=sum(c.cell_type=='code' for c in nb.cells[:index+1])
    nbformat.validate(nb);nbformat.write(nb,FOLDER/'research_companion.ipynb')
    save(FOLDER/'notebook_execution.json',{'status':'All code cells executed top-to-bottom in shared Python namespace; nbformat validated',
        'method':'Direct cell execution with captured streams/images, not nbclient','code_cells':sum(c.cell_type=='code' for c in nb.cells),
        'visual_inspection':'Standalone figures require separate visual inspection; notebook UI was not opened'})


if __name__=='__main__':
    frame,results,baseline=diagnostics();figures(frame,results,baseline);report(results,baseline);notebook()
    print('Saved report, three evidence figures, baseline diagnostics and executed notebook.')
