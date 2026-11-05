"""Portable aggregate notebook/report for the completed bounded model search."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import zipfile
import nbformat
import pandas as pd

from scripts.build_supervisor_model_review import execute, export_html

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/model_validation'
OUT = BASE / '20261021_management_model_search'
FOLDERS = {
    'returns': BASE / '20261021_precision_targets_v2',
    'forecasts': BASE / '20261021_management_forecasts_v2',
    'repurchase': BASE / '20261021_renewal_targets',
    'enquiries': BASE / '20261021_enquiry_conversion',
    'new_data': BASE / '20261021_dosm_inputs/trusted_geography_v2',
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data_dir = OUT / 'data'
    data_dir.mkdir(exist_ok=True)
    forecasting = read(FOLDERS['forecasts'] / 'results.json')
    returns = read(FOLDERS['returns'] / 'results.json')
    repurchase = read(FOLDERS['repurchase'] / 'results.json')
    enquiries = read(FOLDERS['enquiries'] / 'results.json')
    new_data = read(FOLDERS['new_data'] / 'portable_aggregate.json')
    assert len(forecasting) == 4 and len(returns) == 9

    # Explicit safe allowlists: no source customer records, identifiers or credentials.
    save(data_dir / 'forecast_results.json', forecasting)
    for row in forecasting:
        name = row['task'] + '_assessment.csv'
        frame = pd.read_csv(FOLDERS['forecasts'] / name)
        frame[['origin', 'actual', 'visible', 'selected', 'baseline']].to_csv(data_dir / name, index=False)
    classification = []
    return_names = {'each_service_30': 'After each paid service: return within 30 days',
                    'residential_3x_final_30': 'After residential 3rd of 3 visits: return within 30 days',
                    'residential_final_60': 'After final residential paid visit: return within 60 days'}
    for row in returns:
        classification.append({'study': 'Pest-related returns', 'question': return_names[row['target']],
            'policy': row['policy'], 'model': row['family'], 'inputs': row['input_count'],
            **{k: row[k] for k in ['rows', 'positives', 'precision', 'recall', 'accuracy', 'f1', 'threshold', 'TP', 'FP', 'FN', 'TN']},
            'always_no_accuracy': row['always_no_accuracy'], 'passed': row['passes_research_gate'],
            'unique_positive_customers': None})
    for row in repurchase:
        if row['policy'] != 'precision':
            continue
        m = row['assessment']
        repeat = row['population'].startswith('repeat')
        classification.append({'study': 'Repurchase',
            'question': ('Already-repeat customers' if repeat else 'Recent customers') + f": purchase within {row['horizon']} days",
            'policy': row['policy'], 'model': row['selected']['model'], 'inputs': row['selected']['input_count'],
            'rows': m['n'], 'positives': m['positives'],
            **{k: m[k] for k in ['precision', 'recall', 'accuracy', 'f1']},
            'threshold': row['selected']['threshold'],
            **{k.upper(): m[k] for k in ['tp', 'fp', 'fn', 'tn']},
            'always_no_accuracy': 1 - m['prevalence'], 'passed': False,
            'unique_positive_customers': None})
    for row in enquiries['results']:
        m = row['assessment']
        classification.append({'study': 'Enquiries', 'question': 'First staff reply: matching recorded sale in days 1–30',
            'policy': row['policy'], 'model': row['selected']['model'], 'inputs': len(enquiries['inputs']),
            'rows': m['n'], 'positives': m['positives'],
            **{k: m[k] for k in ['precision', 'recall', 'accuracy', 'f1']},
            'threshold': row['selected']['threshold'],
            **{k.upper(): m[k] for k in ['tp', 'fp', 'fn', 'tn']},
            'always_no_accuracy': 1 - m['prevalence'], 'passed': row['research_gate_passed'],
            'unique_positive_customers': None})
    pd.DataFrame(classification).to_csv(data_dir / 'classification_results.csv', index=False)
    shutil.copy2(FOLDERS['new_data'] / 'paired_results.csv', data_dir / 'dosm_results.csv')
    save(data_dir / 'new_data_sources.json', new_data)
    # Exact inputs are kept in a separate lookup, not a 110-column main explanation.
    inputs = []
    source = read(FOLDERS['returns'] / 'source_receipt.json')
    for name, fields in source['feature_sets'].items():
        inputs.extend({'study': 'Returns', 'input_set': name, 'field': field} for field in fields)
    for task in forecasting:
        selected = read(FOLDERS['forecasts'] / f"{task['task']}_selection.json")
        inputs.extend({'study': 'Forecasts', 'input_set': task['task'], 'field': field} for field in selected['feature_names'])
    for name, fields in read(FOLDERS['repurchase'] / 'protocol.json')['features'].items():
        inputs.extend({'study': 'Repurchase', 'input_set': name, 'field': field} for field in fields)
    inputs.extend({'study': 'Enquiries', 'input_set': 'initial_reply', 'field': field} for field in enquiries['inputs'])
    pd.DataFrame(inputs).to_csv(data_dir / 'exact_input_names.csv', index=False)
    pd.read_csv(FOLDERS['repurchase'] / 'summary.csv').to_csv(data_dir / 'repurchase_support.csv', index=False)

    methods = [
        {'Study': 'Planning forecasts', 'Train': 'Earlier timestamp-matured weeks; 52 / 78 / all history',
         'Validation': '12 one-week or 10 two-week origins, Jan–Jun 2026; labels and latest edits before 6 July',
         'Assessment': '14 one-week or 13 overlapping two-week origins, Jul–Oct 2026',
         'Why useful': 'Plan rosters, appointment slots and supplies. Appointment hours are not technician effort.'},
        {'Study': 'Pest-related return targets', 'Train': 'Earlier mature rows; assessment property/programme groups reserved before selection',
         'Validation': 'Up to 3 earlier periods in Jul 2025–Mar 2026, all labels mature before 1 April',
         'Assessment': '1 April–15 July 2026: 976 all-service / 225 third-visit / 270 final-visit rows',
         'Why useful': 'Investigate treatment follow-up risk; formal warranty eligibility stays a separate rule.'},
        {'Study': 'Monthly repurchase', 'Train': 'Mature earlier customer-months; features use only purchases before each month',
         'Validation': 'Earlier 2025 folds, labels mature before 2026 assessment',
         'Assessment': 'Jan–Apr 2026 month-start landmarks; overlapping future purchase windows',
         'Why useful': 'Forecast repeat business; not enough evidence for customer-specific alerts.'},
        {'Study': 'Enquiry to recorded sale', 'Train': 'Jan–Mar 2026: 7,447 contacts / 142 later sale matches',
         'Validation': 'May–Jun 2026: 3,171 / 64, with gaps for 30-day label maturity',
         'Assessment': 'Aug–16 Sep 2026: 1,021 / 30, phone-disjoint; same-day ambiguity excluded',
         'Why useful': 'Would help enquiry conversion, but current source labels and results are weak.'},
        {'Study': 'New DOSM inputs', 'Train': 'Same 1,506 grouped earlier services as existing larger study',
         'Validation': 'Same 1,177 Jul–Nov 2025 services; calibration and threshold chosen here',
         'Assessment': 'Same 2,075 Jan–Aug 2026 services, already inspected historically',
         'Why useful': 'Test whether dated local context adds value; income is district context, not customer income.'},
    ]
    pd.DataFrame(methods).to_csv(data_dir / 'partitions_and_use.csv', index=False)
    provenance = []
    for study, folder in FOLDERS.items():
        for name in ['protocol.json', 'results.json', 'verification.json', 'acceptance.json', 'source_receipt.json']:
            path = folder / name
            if path.exists():
                provenance.append({'study': study, 'project_relative_path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
    save(data_dir / 'source_index.json', provenance)
    counts = {
        'returns': {'attempted_configurations': 90, 'development_and_final_fits': read(FOLDERS['returns'] / 'verification.json')['fits'], 'assessed_policies': 9},
        'repurchase': read(FOLDERS['repurchase'] / 'completion.json'),
        'forecast': read(FOLDERS['forecasts'] / 'verification.json'),
        'enquiry': {'models': enquiries['models_tested'], 'validation_model_threshold_comparisons': enquiries['model_threshold_combinations']},
        'external_inputs': {'paired_variants': len(pd.read_csv(data_dir / 'dosm_results.csv'))},
    }
    # Do not copy arbitrary source completion fields into the share pack.
    counts['repurchase'] = {k: counts['repurchase'][k] for k in ['development_model_fits', 'development_configurations', 'assessment_selected_policies']}
    save(data_dir / 'search_counts.json', counts)

    cells = []
    md = lambda s: cells.append(nbformat.v4.new_markdown_cell(s))
    code = lambda s: cells.append(nbformat.v4.new_code_cell(s))
    md('# Which prediction models are useful for Nomobug?\n\n21 October 2026 · Broader model search · Read this notebook from top to bottom.\n\n**The strongest new directions are planning the next two weeks of bookings and next week’s booked appointment hours.** These passed the declared historical research checks. None of the new yes/no customer or pest-return classifiers is ready for use. The original frozen future test remains unchanged.')
    md('## What management could do with the forecasts\n\nUse the estimated booking total to review the coming roster, available slots and supplies. The forecast starts with appointments already entered in Calendar and estimates later additions. It does not count completed treatments, measure technician productivity or tell staff whom to ignore. All customers can still receive follow-up.\n\n**Important limit:** these are exploratory historical results, not proven live performance. Current surviving Calendar records cannot recreate every past cancellation, move or deleted appointment. A new model does not make an already-inspected test period independent again.')
    md('## 1. Load the checked results\n\nThis notebook uses only the aggregate files supplied in `data/`. It runs offline with pandas, NumPy and Matplotlib; no Google login, private customer export or model refitting is required. The source index identifies the exact project artifacts used. The full training scripts require the private project sources and are deliberately separate from this share pack.')
    code("""from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
DATA = Path('data')
if not DATA.exists():
    matches = [p for p in [Path('outputs/model_validation/20261021_management_model_search/data')] if p.exists()]
    assert matches, 'Open this notebook from its folder, with the supplied data/ directory.'
    DATA = matches[0]
forecast_results = json.loads((DATA / 'forecast_results.json').read_text())
classification = pd.read_csv(DATA / 'classification_results.csv')
plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False,
                     'figure.facecolor': 'white', 'axes.titleweight': 'bold'})
BLUE, AMBER, INK = '#2563eb', '#d58c22', '#182235'
""")
    md('## 2. Planning forecast results\n\nMAE means the average error in one forecast window. Lower is better. **WAPE is an error percentage; 100 minus WAPE is not model accuracy.** The comparator was the best simple baseline on earlier validation, not a deliberately weak baseline. The next-two-week outcomes overlap, so 13 origins represent only six or seven nonoverlapping windows.\n\nThe last outcome window ends 12 October, only two days before the 14 October extraction. Later Calendar revisions are unknown, so that short revision buffer is another reason to verify these candidates on newly saved snapshots.')
    code("""forecast_table = pd.DataFrame([{
    'Question': f"Next {r['horizon_weeks']} week(s): " + ('booking entries' if r['target']=='booking_entries' else 'booked hours'),
    'Model': r['selected']['family'], 'Inputs': r['input_count'],
    'Test origins': r['assessment']['origins'], 'Model MAE': r['assessment']['mae'],
    'Simple baseline MAE': r['baseline_assessment']['mae'],
    'Lower error (%)': 100*r['mae_improvement_fraction'],
    'WAPE (%)': 100*r['assessment']['wape'], 'Research gate': r['research_gate_passed']
} for r in forecast_results])
display(forecast_table.round(2))
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
for ax, target, unit in zip(axes, ['booking_entries','booked_hours'], ['Booking entries', 'Booked appointment hours']):
    rows = [r for r in forecast_results if r['target']==target]
    positions = np.arange(len(rows))
    ax.barh(positions-.16, [r['baseline_assessment']['mae'] for r in rows], .29, label='Strong simple baseline', color=AMBER)
    ax.barh(positions+.16, [r['assessment']['mae'] for r in rows], .29, label='Validation-selected model', color=BLUE)
    ax.set_yticks(positions, [f"Next {r['horizon_weeks']} week(s)" for r in rows])
    ax.set_xlabel('Average absolute error per window'); ax.set_title(unit)
    ax.grid(axis='x', alpha=.15); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9)
fig.suptitle('Later July–October assessment · lower error is better', fontsize=13)
fig.tight_layout(); plt.show()
""")
    md('### Did the forecasts follow the actual pattern?\n\nThe blue line is the selected model, the orange dashed line is the simple comparator, and the black line is the later recorded total. These figures use aggregate booking data. They are not individual customer predictions.')
    code("""fig, axes = plt.subplots(2, 1, figsize=(11, 7.2))
for ax, task, title, unit in zip(axes,
    ['booking_entries_h2','booked_hours_h1'],
    ['Booking entries over the next two weeks', 'Booked appointment hours over the next week'],
    ['Booking entries', 'Booked hours']):
    rows = pd.read_csv(DATA / f'{task}_assessment.csv', parse_dates=['origin'])
    ax.plot(rows.origin, rows.actual, color=INK, lw=2.2, label='Later recorded total')
    ax.plot(rows.origin, rows.selected, color=BLUE, marker='o', ms=3, lw=1.7, label='Selected forecast')
    ax.plot(rows.origin, rows.baseline, color=AMBER, ls='--', label='Strong baseline')
    ax.set_title(title); ax.set_ylabel(unit); ax.grid(alpha=.12)
    ax.legend(frameon=False, ncol=3, fontsize=9)
fig.autofmt_xdate(); fig.tight_layout(); plt.show()
""")
    md('## 3. Yes/no predictions\n\n**Precision:** of the warnings made, how many were correct? **Recall:** of the actual later events, how many were found? A useful model needs both. “No event for anyone” has high accuracy when positive cases are rare.\n\nThe rows below use the precision-focused policies chosen from earlier validation. Populations and target windows differ, so this is not a competition to select the largest number across rows. Return labels mean recorded pest-related returns, not confirmed pest recurrence or every formal warranty claim. A 60-day return is not a 60-day warranty entitlement. One recorded return can label several earlier service windows; positive rows are prediction opportunities, not unique claims. A policy issuing no warnings has undefined precision, displayed as “No warnings”; the source CSV uses zero by convention.')
    code("""selected = classification[classification.policy.eq('precision')].copy()
table = selected[['question','rows','positives','inputs','accuracy','always_no_accuracy','precision','recall','TP','FP','FN']].copy()
table = table.rename(columns={'question':'Prediction question','rows':'Test rows','positives':'Positive rows','inputs':'Inputs',
    'accuracy':'Accuracy %','always_no_accuracy':'Always-no accuracy %','precision':'Correct warnings %','recall':'Events found %',
    'TP':'Correct warnings','FP':'False warnings','FN':'Missed events'})
for column in ['Accuracy %','Always-no accuracy %','Correct warnings %','Events found %']:
    table[column] *= 100
table = table.round(1)
table.loc[table['Correct warnings'].add(table['False warnings']).eq(0), 'Correct warnings %'] = np.nan
display(table.fillna('No warnings'))
assert not selected.passed.any(), 'Revisit the written recommendation if a classifier passed.'
""")
    md('### Why the repeat-purchase sample is smaller than it looks\n\nA customer can appear at several month starts. One purchase can make several overlapping 90-day windows positive. Those are not independent customers or extra purchases. The two already-repeat-customer assessments contain only four and seven positive customers respectively. The table below shows these denominators. No model passed its research gate.')
    code("""support = pd.read_csv(DATA / 'repurchase_support.csv')
display(support[['Population','Horizon days','Test customer-months','Test customers','Positive months','Positive customers','Purchase occasions','Precision %','Recall %']])
""")
    md('## 4. New outside data were downloaded and tested\n\n**DOSM district income, household spending and poverty for 2022:** context about an area, not an estimate of a particular customer’s income. Only the pre-existing 2022 vintage was eligible; the downloaded file also contains later 2024 data, which were excluded. The current download can still contain revisions.\n\n**DOSM consumer prices:** the headline CPI index and year-on-year change, lagged by two months with publication dates checked. A month/date-only control tests whether this is merely acting as a time proxy.\n\nThe paired study keeps the same 1,506 training / 1,177 validation / 2,075 assessment services. It therefore measures the incremental value of these inputs on that historical comparison. It cannot establish a new independent final accuracy result.')
    code("""dosm = pd.read_csv(DATA / 'dosm_results.csv')
dosm_view = dosm[['candidate','input_count','hies_known','cpi_known','rows','positives','accuracy','precision','recall','f1','average_precision','brier_score']].copy()
dosm_view = dosm_view.rename(columns={'candidate':'Inputs compared','input_count':'Input count', 'hies_known':'District data available',
    'cpi_known':'CPI available','rows':'Test rows','positives':'Returns','accuracy':'Accuracy %','precision':'Precision %','recall':'Recall %',
    'f1':'F1','average_precision':'Average precision','brier_score':'Brier error'})
for column in ['Accuracy %','Precision %','Recall %']:
    dosm_view[column] *= 100
display(dosm_view.round(4).fillna('—'))
base = dosm[dosm.candidate.eq('baseline')].iloc[0]
area = dosm[dosm.candidate.eq('plus_hies2022')].iloc[0]
print(f"District data: precision {base.precision:.1%} → {area.precision:.1%}; recall {base.recall:.1%} → {area.recall:.1%}.")
print(f"Trusted district coverage: {int(area.hies_known):,} of {int(area.rows):,} assessment services.")
print('This is a small trade-off, not a high-accuracy breakthrough. Exact public-source URLs, hashes and publication evidence are in data/new_data_sources.json.')
""")
    md('## 5. Which inputs did we actually try?\n\nThe main groups are below. The separate `exact_input_names.csv` lists every technical input name so that this explanation stays readable. Inputs were compared on validation; adding more does not automatically improve the model. Associations and feature importance do not establish causes.')
    code("""display(pd.DataFrame([
    {'Model family':'Planning', 'Inputs in ordinary words':'Appointments already entered; recent booking counts and appointment hours; rolling averages and changes; week/season; nominal festival dates; optional older regional weather', 'Sizes tested':'32 or 36 fields; 52 / 78 / all earlier weeks'},
    {'Model family':'Pest-related return', 'Inputs in ordinary words':'Package and paid-visit stage, pest, premises and past return history; compare adding dated Calendar note flags and earlier/between-visit rain; full environmental set also tested', 'Sizes tested':'28, 39 or 110 fields'},
    {'Model family':'Repurchase', 'Inputs in ordinary words':'How recently and often a customer bought; past gaps and recorded initial sales; package, pest and premises; month; optional older regional weather', 'Sizes tested':'19 or 23 fields'},
    {'Model family':'Enquiry conversion', 'Inputs in ordinary words':'Initial channel, premises, pest, month and weekday. No final conversation status, booking, payment or later remarks.', 'Sizes tested':'7 fields'},
    {'Model family':'New-data paired return test', 'Inputs in ordinary words':'Original 93; add district2022 income/spending/poverty/unknown flag; or old CPI level/change; or both; date proxy as a control', 'Sizes tested':'93 to 99 fields, plus separate date control'},
]))
""")
    md('## 6. Partitions and leakage checks\n\nValidation selects the algorithm, inputs and warning threshold. The later assessment measures those fixed choices. We used chronological periods, outcome-maturity gaps and customer/property separation where the target required it. We did not try random splits and choose the one with the largest assessment score. All results remain historical research because these periods have already been explored.\n\nThe return feature snapshot does not retain a known-at timestamp for every historical input. Source hashes and observation-date windows can be checked, but this does not certify the exact weather/data vintage available at each past service. The booking forecast uses a seven-day lag for old regional weather; this still does not reconstruct past Calendar versions.\n\nTwo first attempts were excluded and retained: the forecast validation used a few later-edited labels; the first return-target run allowed assessment properties into earlier model selection even though final fitting was purged. The corrected versions exclude these records before selection. The earlier invalid repurchase attempt is also retained and disclosed in its study. Corrections were based on timing/group rules, not choosing prettier results.')
    code("""display(pd.read_csv(DATA / 'partitions_and_use.csv'))
counts = json.loads((DATA / 'search_counts.json').read_text())
display(pd.DataFrame([
    {'Study':'Pest-related return targets', 'Search':'90 configurations; 9 fixed assessment policies'},
    {'Study':'Monthly repurchase', 'Search':f"{counts['repurchase']['development_configurations']} feasible configurations; {counts['repurchase']['development_model_fits']} development fits"},
    {'Study':'Booking planning', 'Search':f"{counts['forecast']['attempted_configurations']} attempted; {counts['forecast']['development_configurations']} complete; {counts['forecast']['infeasible_configurations']} infeasible"},
    {'Study':'Enquiry conversion', 'Search':f"{counts['enquiry']['models']} models; {counts['enquiry']['validation_model_threshold_comparisons']} validation threshold comparisons"},
    {'Study':'New outside data', 'Search':f"{counts['external_inputs']['paired_variants']} corrected paired variants"},
]))
""")
    md('## 7. What should go into the capstone?\n\n**Keep as the strongest new candidates:** the next-two-week booking forecast and next-week booked-hours forecast, with their simple comparators and clear error charts. They help with short-term planning and must be checked on newly saved, complete Calendar snapshots before operational claims.\n\n**Keep experimental:** the original frozen pest-return model and its existing future test. These searches have not produced a reliable replacement. Do not present the best score across different targets as one universal model accuracy.\n\n**Do not promote:** the new repurchase and enquiry models. Their warnings are mostly wrong, and some positive samples are very small. Payment reminders, current balances and warranty eligibility remain source-backed rules/reporting rather than artificial prediction targets.\n\n**Data still missing for other useful targets:** verified actual treatment duration, reasons and true versions for rescheduling, payment settlement history/due amounts, building completion year and dated building-level pest complaints. Current maps or today’s online reports cannot be assumed to describe a building before a historical prediction. We did not fabricate these labels or claim that every possible dataset/model has been tested.')
    md('## Sources and reproduction\n\nOfficial data: [DOSM district household income and expenditure](https://data.gov.my/data-catalogue/hies_district) and [DOSM CPI](https://data.gov.my/data-catalogue/cpi_headline). Method references: [time-series cross-validation](https://otexts.robjhyndman.com/fpp3/tscv.html) and [threshold tuning](https://scikit-learn.org/stable/auto_examples/model_selection/plot_tuned_decision_threshold.html).\n\nThe source index provides exact artifact paths and SHA-256 hashes. It contains no customer records. Re-running this notebook redraws the saved aggregate results; it does not retrain the models. Native Jupyter kernel execution was unavailable, so the cells were executed top to bottom with the project’s Python notebook executor and the saved figures inspected.')
    code("""display(pd.DataFrame(json.loads((DATA / 'source_index.json').read_text())))
""")
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata['kernelspec'] = {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}
    notebook.metadata['language_info'] = {'name': 'python', 'version': '3'}
    # The executor runs in the artifact directory to validate the same portable inputs.
    import os
    original = Path.cwd()
    try:
        os.chdir(OUT)
        execute(notebook)
    finally:
        os.chdir(original)
    nbformat.validate(notebook)
    path = OUT / 'Management_Model_Search.ipynb'
    nbformat.write(notebook, path)
    export_html(notebook, OUT / 'Management_Model_Search.html')
    html_path = OUT / 'Management_Model_Search.html'
    content = html_path.read_text(encoding='utf-8').replace('<title>CP2 model review</title>', '<title>Nomobug — management model search</title>')
    content = content.replace('<body>', '<body><p><a href="Management_Model_Search.ipynb">Jupyter notebook</a> · <a href="Management_Model_Search_Share.zip">Share pack</a> · <a href="data/classification_results.csv">Exact classifier results</a></p>', 1)
    html_path.write_text(content, encoding='utf-8')
    for i, cell in enumerate(notebook.cells):
        for j, output in enumerate(cell.get('outputs', [])):
            encoded = output.get('data', {}).get('image/png')
            if encoded:
                import base64
                (OUT / f'figure_{i}_{j}.png').write_bytes(base64.b64decode(encoded))
    save(OUT / 'manifest.json', {'built_at_utc': datetime.now(timezone.utc).isoformat(),
        'notebook_format_valid': True, 'sequential_execution': True,
        'error_outputs': sum(o.output_type == 'error' for c in notebook.cells for o in c.get('outputs', [])),
        'scope': 'Aggregate portable comparison. No production promotion. Corrected historical studies; no fresh-holdout claim.',
        'artifacts': {p.name: sha(p) for p in [path, html_path]},
        'sources': provenance})
    archive = OUT / 'Management_Model_Search_Share.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as handle:
        for item in [path, html_path, OUT / 'manifest.json', *sorted(data_dir.glob('*'))]:
            handle.write(item, item.relative_to(OUT))
    print(json.dumps({'notebook': str(path), 'cells': len(cells), 'classifiers': len(classification), 'forecasts': len(forecasting), 'zip_bytes': archive.stat().st_size}))


if __name__ == '__main__':
    main()
