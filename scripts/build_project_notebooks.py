"""Build the project notebook series and a non-destructive project file catalogue.

Reads pinned research evidence. Chapter 09 can replay the selected fit when its
private rows exist; no model search, deployment, source edit or prediction logging.
Run: .venv/Scripts/python.exe -m scripts.build_project_notebooks
"""
from pathlib import Path
import ast
import hashlib
import html
import json
import shutil
import zipfile
from datetime import datetime, timezone

import nbformat
import pandas as pd

from scripts.build_supervisor_model_review import execute, export_html

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'notebooks'
DATA = OUT / 'evidence'
REVIEW = ROOT / 'outputs/supervisor_model_review/20261017/data'
SEARCH = ROOT / 'outputs/model_validation/20261021_management_model_search/data'
AUDIT = ROOT / 'outputs/project_audit/20261026_structure'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding='utf-8')


def copy_evidence(source, name=None):
    source = Path(source)
    destination = DATA / (name or source.name)
    shutil.copy2(source, destination)
    return {'source': source.relative_to(ROOT).as_posix(),
            'copy': destination.relative_to(OUT).as_posix(), 'sha256': sha(source)}


SETUP = '''from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt
BASE = Path.cwd()
if not (BASE / "evidence").exists():
    BASE = BASE / "notebooks" 
assert (BASE / "evidence").is_dir(), "Open from the project root or notebooks."
EVIDENCE = BASE / "evidence"
def read_json(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8-sig"))
pd.set_option("display.max_colwidth", 90)
plt.rcParams.update({"figure.figsize": (10, 4.5), "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 11})
'''


def notebook(name, title, sections):
    cells = [nbformat.v4.new_markdown_cell('# ' + title), nbformat.v4.new_code_cell(SETUP)]
    for kind, value in sections:
        cells.append(nbformat.v4.new_markdown_cell(value) if kind == 'md' else nbformat.v4.new_code_cell(value))
    nb = nbformat.v4.new_notebook(cells=cells, metadata={
        'kernelspec': {'name': 'python3', 'display_name': 'Python 3', 'language': 'python'},
        'language_info': {'name': 'python'},
        'cp2': {'scope': 'Pinned aggregate evidence; no new training or prospective evaluation', 'built': '2026-10-28'}})
    execute(nb)
    nbformat.validate(nb)
    nbformat.write(nb, OUT / (name + '.ipynb'))
    export_html(nb, OUT / (name + '.html'))
    rendered=OUT/(name+'.html')
    rendered.write_text(rendered.read_text(encoding='utf-8').replace('<title>CP2 model review</title>','<title>'+html.escape(title)+'</title>'),encoding='utf-8')
    return {'file': name + '.ipynb', 'title': title, 'executed_cells': sum(c.cell_type == 'code' for c in cells)}


def describe(path):
    label = path.stem.replace('_', ' ').replace('-', ' ')
    purpose = ''
    if path.suffix == '.py':
        try:
            purpose = (ast.get_docstring(ast.parse(path.read_text(encoding='utf-8-sig'))) or '').split('\n')[0]
        except (SyntaxError, UnicodeError):
            pass
    elif path.suffix in {'.md', '.sql', '.yaml', '.yml'}:
        lines = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()
        purpose = next((s.strip('# -') for s in lines[:12] if s.startswith(('# ', '-- '))), '')
    return label.title(), purpose or label.capitalize()


def category(path):
    p = path.as_posix()
    if p.startswith('notebooks'): return 'Project notebooks'
    if p.startswith('archive'): return 'Retired code - reference only'
    if p.startswith('notebooks'): return 'Project notebooks'
    if p.startswith('dbt/models/gold'): return 'Management reporting SQL'
    if p.startswith('dbt/models/analytics_ml'): return 'Model data and historical results SQL'
    if p.startswith('dbt'): return 'Data cleaning and validation SQL'
    if p.startswith('webapp'): return 'Website and AI'
    if p.startswith('tests'): return 'Automated checks'
    if p.startswith('config'): return 'Source mappings and model protocols'
    if p.startswith(('infra', '.github')) or path.name.startswith(('Dockerfile','cloudbuild','compose')): return 'Cloud and containers'
    if p.startswith('planning'): return 'Project records and specifications'
    if p.startswith('templates'): return 'Input templates'
    if p.startswith('scripts'):
        s = path.stem
        if any(w in s for w in ['geocod','geoapify','postcode','location','property_alias']): return 'Location matching'
        if any(w in s for w in ['weather','flood','environment','hotosm','worldcover','dosm','holiday','food','building','predictor_source']): return 'External data and predictors'
        if any(w in s for w in ['model','callback','warranty','research','predictor','forecast','stepwise','forward_select']): return 'Prediction and evaluation'
        if any(w in s for w in ['load','extract','source','silver','gold','payment','calendar','sales','bronze','release']): return 'Data preparation and reporting'
        return 'Project utilities'
    return 'Project configuration'


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    pointer_path = ROOT / 'config/cp2_model_current.json'
    protected_before = {str(p.relative_to(ROOT)): sha(p) for p in [pointer_path,
        ROOT/'outputs/cp2-v2/prospective_callback_v2/bundle.json',
        ROOT/'outputs/cp2-v2/prospective_callback_v2/challenger_all_history.joblib',
        ROOT/'config/cp2_planning_v1.json']}
    sources = []
    # Aggregate allowlist only. Never copy source rows, tokens or customer identifiers.
    for name in ['review_metadata.json', 'source_catalog.json', 'development_partitions.csv',
                 'variables_plain_english.csv', 'numeric_associations.csv', 'group_decisions.csv',
                 'individual_removal_decisions.csv', 'model_results.json']:
        sources.append(copy_evidence(REVIEW/name))
    for name in ['forecast_results.json', 'classification_results.csv', 'partitions_and_use.csv',
                 'exact_input_names.csv', 'new_data_sources.json', 'dosm_results.csv',
                 'booking_entries_h2_assessment.csv', 'booked_hours_h1_assessment.csv']:
        sources.append(copy_evidence(SEARCH/name))
    sources.append(copy_evidence(ROOT/'outputs/model_validation/20261018_model_register/Study_Summary.csv', 'historical_studies.csv'))
    sources.append(copy_evidence(ROOT/'outputs/model_validation/20261018_model_register/Declared_Input_Lists.csv', 'historical_input_lists.csv'))
    sources.append(copy_evidence(ROOT/'config/cp2_planning_v1.json', 'planning_protocol.json'))
    calibration_study=ROOT/'outputs/model_validation/20261028_probability_calibration'
    if (calibration_study/'results.json').exists():
        sources.append(copy_evidence(calibration_study/'results.json','probability_calibration_results.json'))
        sources.append(copy_evidence(calibration_study/'validation_metrics.csv','probability_calibration_validation.csv'))
        sources.append(copy_evidence(calibration_study/'assessment_metrics.csv','probability_calibration_assessment.csv'))
    # Save only numerical outcome/probability pairs: no sale IDs, dates or customer fields.
    predictions = pd.read_csv(ROOT/'outputs/cp2-v2/model_corrected_v5/selected_ap_predictions_private.csv')
    predictions[['probability','threshold','warranty_signal_within_30d']].to_csv(DATA/'return_test_predictions.csv', index=False)
    sources.append({'source':'outputs/cp2-v2/model_corrected_v5/selected_ap_predictions_private.csv',
                    'source_sha256':sha(ROOT/'outputs/cp2-v2/model_corrected_v5/selected_ap_predictions_private.csv'),
                    'copy':'evidence/return_test_predictions.csv', 'sha256':sha(DATA/'return_test_predictions.csv'),
                    'projection':'Only outcome, probability and threshold; no identifiers'})
    sql_files=['sales.sql','payments.sql','recurring_payments.sql','calendar_events.sql','calendar_event_matches.sql',
               'calendar_event_weather.sql','analytics_ml/warranty_callback_fixed_horizon_dataset.sql']
    rules=[]
    for name in sql_files:
        p=ROOT/'dbt/models'/name
        if p.exists():
            target=DATA/'sql'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,target)
            rules.append({'source':p.relative_to(ROOT).as_posix(),'copy':target.relative_to(OUT).as_posix(),'sha256':sha(p)})
    sources += rules
    code_dir=DATA/'code';code_dir.mkdir(exist_ok=True)
    for filename,names in {
        'compare_callback_candidates_v2.py':['make_pipeline','fit_member','prepare_input'],
        'benchmark_warranty_models.py':['purged_split','make_model','fit_calibrator','select_threshold'],
    }.items():
        original=ROOT/'scripts'/filename
        text=original.read_text(encoding='utf-8-sig')
        tree=ast.parse(text)
        excerpts=[ast.get_source_segment(text,node) for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        destination=code_dir/filename
        destination.write_text('\n\n'.join(excerpts)+'\n',encoding='utf-8')
        sources.append({'source':original.relative_to(ROOT).as_posix(),'source_sha256':sha(original),
                        'copy':destination.relative_to(OUT).as_posix(),'sha256':sha(destination),'projection':'Production function excerpts; not a standalone module'})
    dictionary=pd.read_csv(ROOT/'config/operational_column_dictionary.csv')
    dictionary.to_csv(DATA/'source_column_dictionary.csv',index=False)
    write_json(DATA/'model_configuration.json', {k:read(pointer_path)[k] for k in
        ['version','primary_model','primary_selection','target','target_type','output','training_services','training_callbacks','new_retrospective_test','recovery_cohort','recovery_earliest_final_evaluation']})
    write_json(DATA/'source_checks.json',read(REVIEW/'review_metadata.json')['checks'])
    write_json(DATA/'source_manifest.json',sources)
    books=[]
    books.append(notebook('00_Project_Overview','Nomobug Capstone Project',[
      ('md','''## Project purpose
Connect Sales, Calendar, contract reminder records and environmental context to management reporting, customer follow-up and experimentally evaluated predictions.

## Reading order
1. **Data Sources** — what each source records and what one row means.
2. **Data Cleaning** — how types, duplicate records, dates and service links are treated.
3. **Outcome Labels and Partitions** — what is predicted and which records are used for fitting, validation and assessment.
4. **Predictors** — every input, its meaning, observed association and removal-test evidence.
5. **Pest Return Model** — configuration, training code and historical classification results.
6. **Weekly Planning Models** — separate booking and appointment-hour forecasts.
7. **Model Experiments** — historical alternatives, inputs and results.

These notebooks replay pinned aggregate evidence. They do not train a new model, change its weights or manufacture future results. Production source commands and code paths are identified in the relevant chapter. The source snapshots remain private in the project.'''),
      ('code', '''m = read_json("model_configuration.json")
display(pd.DataFrame([
    {"Model": "Pest-related return", "Question": "Recorded return within 30 days after a paid service?", "Inputs": 93, "Status": "Frozen experimental model"},
    {"Model": "Bookings", "Question": "How many Calendar bookings over the next two weeks?", "Inputs": 36, "Status": "Historical candidate; separate live test"},
    {"Model": "Appointment hours", "Question": "How many booked team-hours next week?", "Inputs": 32, "Status": "Historical candidate; separate live test"}
]))'''),
      ('md','''## Project files
Open `FILE_GUIDE.html` at the project root for the searchable file catalogue. `notebooks` contains this reading series. `scripts` contains executable processing and model code. `dbt/models` contains cleaning and reporting SQL. `config` contains rules, protocols and frozen pointers. `outputs` contains dated evidence; it is not a list of current models.

The website is an operational interface. Looker Studio is the management dashboard. Neither a Calendar booking nor a green reminder-date cell proves a completed treatment or a payment.''')]))
    books.append(notebook('01_Data_Sources','Data Sources',[
      ('md','''## Source records
The source tabs have different grains. Joining their rows and summing everything would duplicate sales or visits. Recorded sales are package prices, not profit or settled cash. The PAYMENTS tab is not sufficiently maintained to act as the payment-tracking authority.'''),
      ('code','''sources = pd.DataFrame([
    ["Sales", "One sale/package record", "Package, price, customer and service linkage"],
    ["Commercial Clients", "One source client/contract record", "Commercial context and contract matching"],
    ["Calendar", "One event in a particular source snapshot", "Bookings, cancellations, service stages and recorded returns"],
    ["Recurring Payments", "One tracked contract, with reminder-date columns", "Reminder dates and recorded cumulative paid/balance amounts"],
    ["Payments", "One recorded payment entry", "Coverage/reconciliation checks; not reliable current paid status"],
    ["Refund", "One source refund record", "Refunds shown separately from sales"],
    ["Weather and geography", "Location/date or mapped feature", "Environmental predictors with availability limits"]
], columns=["Source", "One row means", "Use"])
display(sources)
columns = pd.read_csv(EVIDENCE / "source_column_dictionary.csv")
display(columns.groupby("source_tab", as_index=False).size().rename(columns={"size":"Documented columns"}))'''),
      ('md','''## External data
The following register records identified sources and their limits. Identified or downloaded does not automatically mean retained in the frozen model. Actual building age is unavailable; neighbourhood settlement age is a different proxy. Online silence does not mean a building has no pest history.'''),
      ('code','''external = pd.DataFrame(read_json("source_catalog.json"))
display(external[["predictor", "source", "status", "time_limit"]])'''),
      ('md','''## Warehouse layers
`bronze`: immutable source snapshots. `silver`: cleaned and linked records. `gold`: approved management views. `analytics_ml`: historical research tables. `audit`: pipeline and collection evidence. `quality`: data checks.

Source extraction: `scripts/load_operational_bronze.py`, `scripts/load_calendar_bronze.py`. Live reporting entry point: `scripts/cp2_reporting_release.py`. See `planning/BIGQUERY_START_HERE.md` and the live warehouse catalogue in `project_guide`.

Credentials are not needed to read this notebook. Live extraction requires the project's approved read-only Google source access.''')]))
    books.append(notebook('02_Data_Cleaning','Data Cleaning',[
      ('md','''## Transformation sequence
Source snapshots → parse values and dates → classify Calendar events → match services to sales/programmes → attach location and weather → derive outcome windows and predictors → validate and publish.

The production transformations are SQL/dbt and Python scripts. This chapter contains their exact SQL and archived model-input checks, rather than a second implementation with different rules.'''),
      ('code','''cleaning = pd.DataFrame([
    ["Money and dates", "Keep original values; parse analytical types; preserve invalid/missing values", "dbt/models/sales.sql; payments.sql; recurring_payments.sql"],
    ["Calendar classification", "Separate cancelled, administrative, parked, scheduled and corrective-return events", "dbt/models/calendar_events.sql"],
    ["Temporary placeholders", "Use exact owner-confirmed event and time; never classify every Sunday as parked", "scripts/calendar_appointment_policy.py"],
    ["Programme linkage", "Link confirmed 1x + Upsell 2x or combined programmes; preserve separate sale rows", "scripts/service_programme_policy.py; dbt/models/calendar_event_matches.sql"],
    ["Payment reminders", "Dates are reminders; green only means the date passed; paid totals come from recorded amounts", "scripts/sales_payment_rules.py"],
    ["Location matching", "Queue ambiguous addresses; do not replace missing precise locations with a false exact point", "scripts/cp2_geocoding.py"],
    ["Time availability", "Only attach information available by prediction time", "scripts/callback_live_features.py; callback_live_weather.py"]
], columns=["Step", "Rule", "Implementation"])
display(cleaning)'''),
      ('md','''## Sales transformation
The following is copied from the actual dbt model. The full file is retained in `evidence/sql/sales.sql`; source hashes are listed in `source_manifest.json`.'''),
      ('code','''sales_sql = (EVIDENCE / "sql/sales.sql").read_text(encoding="utf-8-sig")
print("\\n".join(sales_sql.splitlines()[:65]))'''),
      ('md','''## Calendar transformation
Cancellation and administrative rules take priority. A moved temporary placeholder expires its exact-slot override. A rescheduled event is not an additional completed paid visit. Event identity is retained independently of changing source row numbers.'''),
      ('code','''calendar_sql = (EVIDENCE / "sql/calendar_events.sql").read_text(encoding="utf-8-sig")
print("\\n".join(calendar_sql.splitlines()[:48]))'''),
      ('md','''## Archived model-input checks
These are the recorded checks on the 5,695-row frozen-refit input, not a fresh audit of today's Google records. Two weather-date values were missing; missing coverage is retained as a limitation.'''),
      ('code','''checks = read_json("source_checks.json")
display(pd.DataFrame([{"Check":k.replace("_"," "), "Recorded count":v} for k,v in checks.items()]))
assert checks["duplicate_service_keys"] == 0
assert checks["unresolved_labels"] == 0
assert checks["non_30_day_windows"] == 0
assert checks["outcomes_after_observation"] == 0
assert checks["weather_on_or_after_service"] == 0'''),
      ('md','''## Reproduce from the private input
From the project root, `python -m scripts.build_supervisor_model_review` reloads the hash-pinned input, calls `benchmark_warranty_models.load_dataset_input` and `compare_callback_candidates_v2.prepare_input`, and computes these aggregate checks. It writes review artifacts only; it does not publish or retrain.

Production SQL checks run through `scripts/cp2_reporting_release.py`; run its help before using release options. Do not run every script in the folder: some publish, renew credentials or evaluate an experiment once.''')]))
    books.append(notebook('03_Outcome_Labels_and_Partitions','Outcome Labels and Partitions',[
      ('md','''## Prediction question
**Will a pest-related corrective return be recorded within 30 days after this paid service?** Yes = 1; No = 0. A normal next paid visit does not become a return label. A recorded corrective visit is not independent proof of pest recurrence or a verified formal warranty claim. Cancellations and unresolved/immature outcomes must not become negative examples.

## Business rules and model labels
Commercial clients have no warranty entitlement. Residential 1x has none. A confirmed 1x plus Upsell 2x is treated as a linked 3-service programme. Residential 3x allows the confirmed post-third-service warranty window; a scheduling delay beyond 14 days does not automatically remove eligibility. Residential 4x, 6x and 12x cover the service period plus 30 days after the final visit, regardless of pest. These entitlement rules and the model's recorded-return target are related but different concepts.'''),
      ('code','''metadata = read_json("review_metadata.json")
display(pd.DataFrame([
    ["Earlier development pool (EDA)", metadata["eda_services"], metadata["eda_returns"]],
    ["Maturity gap (not added to earlier EDA or held-out assessment)", metadata["maturity_gap_services"], None],
    ["Historical assessment", metadata["holdout_services"], metadata["holdout_returns"]],
    ["Final later prospective refit (includes all mature input)", metadata["total_refit_services"], metadata["total_refit_returns"]]
], columns=["Role", "Services", "Recorded positive windows"]))
assert metadata["eda_services"] + metadata["maturity_gap_services"] + metadata["holdout_services"] == metadata["total_refit_services"]
display(pd.read_csv(EVIDENCE / "development_partitions.csv"))'''),
      ('md','''## Why the assessment has 100 services
The 100 are the reserved later-date assessment, not the entire dataset or 100 warranty visits. Five had recorded returns; 95 did not. The prospective refit was fitted later on 5,695 mature services; it must not be evaluated on those fitting rows as if they were unseen.

Development uses chronological folds with outcome embargo and property-group purging. The archived audit reports 34 development/assessment shared groups: the later historical assessment is not an entirely unseen-property test. Other larger historical studies are catalogued separately; they cannot be pooled as one untouched test.

## Future evaluation
The recovery cohort is 16–30 October, with earliest full outcome evaluation 30 November, conditional on complete timely predictions and outcomes. Missed or late predictions remain missing. This notebook does not check current collection health or claim a completed future result. Exact protocol: `config/cp2_recovery_cohort.json`.''')]))
    books.append(notebook('04_Predictors','Predictors',[
      ('md','''## Input groups
The original model uses 93 inputs, expanded to 238 encoded columns. Inputs are not learned parameters. The main table below groups them; the full dictionary at the end names every input and explains its type, missingness and observed relationship.'''),
      ('code','''variables = pd.read_csv(EVIDENCE / "variables_plain_english.csv")
assert len(variables) == 93
groups = variables.groupby("Group").size().sort_values()
display(groups.rename("Inputs").reset_index())
groups.plot.barh(color="#2563eb")
plt.xlabel("Input count"); plt.ylabel(""); plt.title("Original model input groups")
plt.tight_layout(); plt.show()'''),
      ('md','''## Observed relationships
These are pairwise correlations on earlier development data only. A positive value means higher observed input values tend to appear with more return labels; a negative value means the opposite. Correlation does not establish causality, individual significance or benefit when added to the model.'''),
      ('code','''association = pd.read_csv(EVIDENCE / "numeric_associations.csv")
names = variables.set_index("Technical field")["Variable"].to_dict()
association["Input"] = association["feature"].map(names).fillna(association["feature"])
shown = association.dropna(subset=["spearman_rho"]).assign(magnitude=lambda d:d.spearman_rho.abs()).nlargest(12,"magnitude").sort_values("spearman_rho")
plt.barh(shown.Input, shown.spearman_rho, color=["#2563eb" if x>=0 else "#f59e0b" for x in shown.spearman_rho])
plt.axvline(0,color="#64748b",lw=.8); plt.xlim(-1,1)
plt.xlabel("Spearman correlation with recorded 30-day return"); plt.title("Largest observed associations · development data")
plt.tight_layout(); plt.show()'''),
      ('md','''## Did removing inputs help?
The group-removal table compares the same chronological validation periods. AP measures probability ranking; Brier measures probability error (lower is better). Neither is a causal effect. Individual removal is exploratory: selecting many changes from one validation set can overfit it. No new input is automatically added to the frozen model.'''),
      ('code','''display(pd.read_csv(EVIDENCE / "group_decisions.csv").round(4))
removal = pd.read_csv(EVIDENCE / "individual_removal_decisions.csv")
print("Individual-removal records:", len(removal))
display(removal)'''),
      ('md','''## All original inputs
The table gives the exact technical field for tracing the scripts alongside the reader-facing name. Building age and complete online building pest history are unavailable. Neighbourhood settlement age, holiday, rainfall-between-visit, food and facility experiments belong to separate candidate studies; their results are in chapter 7.'''),
      ('code','''for group_name, group in variables.groupby("Group", sort=True):
    print(group_name)
    display(group[["Variable", "What it means", "Type", "Missing (%)", "Observed relationship", "Technical field"]].reset_index(drop=True))''')]))
    books.append(notebook('05_Pest_Return_Model','Pest Return Model',[
      ('md','''## Training configuration
The current experimental reference is Extra Trees: 300 trees, maximum depth 10 and minimum leaf size 5. Its historical assessed fit and the later all-mature-data prospective refit have different purposes. Thresholds are selected using validation, never by taking the best score on the final assessment.'''),
      ('code','''configuration = read_json("model_configuration.json")
display(pd.DataFrame([{"Setting":k.replace("_"," "),"Value":str(configuration[k])} for k in ["primary_model","target","target_type","output","training_services","training_callbacks"]]))'''),
      ('md','''## Model construction
Production code: `scripts/compare_callback_candidates_v2.py` → `make_pipeline`, `fit_member`, `evaluate_development`, `select_candidates`, `fit_artifact`. Feature preparation: `prepare_input`; split/metrics utilities: `scripts/benchmark_warranty_models.py`.

The preprocessing pipeline imputes missing numeric inputs and encodes categorical inputs within fitting. Calibration and threshold selection use development evidence. The reproducible full training command is `python -m scripts.compare_callback_candidates_v2 --help` to select the declared input/output options. This chapter does not rerun fitting or overwrite any artifacts.

## Historical assessment
The following metrics are recalculated from the saved numerical predictions for the exact 100-service assessment. These are not predictions from a new retraining and not prospective performance.'''),
      ('code','''from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, brier_score_loss, confusion_matrix
p = pd.read_csv(EVIDENCE / "return_test_predictions.csv")
y = p.warranty_signal_within_30d.astype(int)
predicted = (p.probability >= p.threshold).astype(int)
assert len(y)==100 and y.sum()==5
metrics = {"Accuracy":accuracy_score(y,predicted),"Precision":precision_score(y,predicted,zero_division=0),
           "Recall":recall_score(y,predicted,zero_division=0),"F1":f1_score(y,predicted,zero_division=0),
           "ROC AUC":roc_auc_score(y,p.probability),"Average precision":average_precision_score(y,p.probability),
           "Brier probability error":brier_score_loss(y,p.probability),"Always-no-return accuracy":(y==0).mean()}
display(pd.DataFrame(metrics.items(),columns=["Metric","Value"]).round(4))
matrix = confusion_matrix(y,predicted)
fig,ax=plt.subplots(figsize=(6,4)); ax.imshow(matrix,cmap="Blues")
for (i,j),v in __import__("numpy").ndenumerate(matrix): ax.text(j,i,str(v),ha="center",va="center",fontsize=20,color="white" if v>50 else "#172554")
ax.set(xticks=[0,1],yticks=[0,1],xticklabels=["No return","Return"],yticklabels=["No return","Return"],xlabel="Predicted",ylabel="Recorded outcome",title="Historical assessment · 100 services, 5 positives")
plt.tight_layout();plt.show()
assert abs(metrics["Accuracy"]-.94)<1e-9 and abs(metrics["Precision"]-.4)<1e-9'''),
      ('md','''## Training implementation
These are the exact production functions copied from `scripts/compare_callback_candidates_v2.py`, including estimator settings, fitting and feature preparation. They are shown for inspection; executing this chapter does not refit or overwrite the frozen model. The supporting preprocessing, purged split, calibration and threshold functions are in `evidence/code/benchmark_warranty_models.py`.'''),
      ('code','''print((EVIDENCE / "code/compare_callback_candidates_v2.py").read_text())'''),
      ('md','''## Interpretation
Two recorded returns were identified, three were missed and three false alerts were issued. 94% accuracy is below the 95% always-no-return baseline. Five positive cases are too few to establish reliable sensitivity or precision. The model remains experimental.

Verify the frozen bundle locally with `python scripts/cp2_model.py verify`. Do not use the 5,695 training replay as independent accuracy evidence. Prediction collection is handled by `scripts/cp2_cloud_collector.py`; one-time future evaluation follows the declared recovery protocol.''')]))
    partial=ROOT/'outputs/project_audit/20261101_outcome_repair/partial_evaluation.json'
    if partial.exists():
        safe={k:v for k,v in read(partial).items() if k!='excluded_private'}
        write_json(DATA/'matured_partial_20261101.json',safe)
        pest=OUT/'05_Pest_Return_Model.ipynb'
        nb=nbformat.read(pest,as_version=4)
        nb.cells.extend([
            nbformat.v4.new_markdown_cell("""## Partial future test — 1 November 2026
Fresh read-only Calendar and Sheets extraction verified outcomes through 31 October. Fourteen immutable predictions for 30 September–1 October have completed outcome windows and match the original Calendar appointment identities. This is the available timely-prediction subset, not the complete experiment population.

There was one recorded pest-related return. The frozen model flagged no services and missed that return: 92.9% accuracy, equal to always predicting no return; recall 0%. Precision is undefined because there were no positive predictions. This small partial sample does not establish improved performance.

The recovery cohort still records 24 missed eligible predictions and 16 unresolved candidate windows. Those historical gaps are preserved. No final cohort evaluator was run, no late prediction was backfilled and no model threshold was changed. Script: `scripts/evaluate_matured_cp2_subset.py`."""),
            nbformat.v4.new_code_cell("""partial = read_json('matured_partial_20261101.json')
metrics = partial['metrics']
display(pd.DataFrame([{'Services':metrics['rows'], 'Recorded returns':metrics['positives'], 'Accuracy':metrics['accuracy'], 'Precision':metrics['precision'], 'Recall':metrics['recall'], 'Always-no-return accuracy':metrics['always_no_return_accuracy']}]))
fig, ax = plt.subplots(figsize=(8, 3.5))
labels = ['Correct no-return', 'Missed return', 'False warning', 'Correct return warning']
values = [metrics['true_negative'], metrics['false_negative'], metrics['false_positive'], metrics['true_positive']]
ax.barh(labels, values, color=['#2563eb','#d55e00','#e69f00','#009e73'])
ax.set_xlabel('Services (14 matured predictions)'); ax.set_title('One return recorded; model raised no warnings')
ax.set_xlim(0,15)
for index,value in enumerate(values): ax.text(value+.15,index,str(value),va='center')
fig.tight_layout(); plt.show()
""")])
        execute(nb);nbformat.validate(nb);nbformat.write(nb,pest);export_html(nb,OUT/'05_Pest_Return_Model.html')
        next(b for b in books if b['file']=='05_Pest_Return_Model.ipynb')['executed_cells']+=1
    books.append(notebook('06_Weekly_Planning_Models','Weekly Planning Models',[
      ('md','''## Separate prediction questions
Bookings: Calendar service-like entries in the next two weeks. Appointment hours: booked team-slot duration in the next week. These are not completed treatments or productive employee-hours. Regression uses error metrics, not classification precision/accuracy.

The algorithms and input formulas are fixed in `config/cp2_planning_v1.json`. They refit weekly only on earlier matured windows. Historical comparisons repeatedly examined Calendar snapshots; new live outcomes must be reported separately.'''),
      ('code','''protocol = read_json("planning_protocol.json")
rows=[]
for task in protocol["targets"]:
    recorded = pd.read_csv(EVIDENCE / (task["task"]+"_assessment.csv"))
    error = recorded.selected - recorded.actual
    baseline_error = recorded.baseline - recorded.actual
    mae=error.abs().mean(); baseline_mae=baseline_error.abs().mean()
    assert abs(mae-task["assessment"]["mae"])<1e-6
    rows.append({"Target":task["task"], "Algorithm":task["selected"]["id"], "Inputs":task["input_count"],
                 "Assessment windows":len(recorded),"MAE":mae,"RMSE":(error.pow(2).mean())**.5,
                 "WAPE (%)":100*error.abs().sum()/recorded.actual.abs().sum(),"Baseline MAE":baseline_mae,
                 "MAE reduction (%)":100*(1-mae/baseline_mae)})
display(pd.DataFrame(rows).round(2))
fig,axes=plt.subplots(2,1,figsize=(10,7))
for ax,task in zip(axes,protocol["targets"]):
    recorded=pd.read_csv(EVIDENCE/(task["task"]+"_assessment.csv"))
    dates=pd.to_datetime(recorded.origin)
    ax.plot(dates,recorded.actual,label="Recorded",color="#111827",marker="o")
    ax.plot(dates,recorded.selected,label="Model",color="#2563eb")
    ax.plot(dates,recorded.baseline,label="Baseline",color="#f59e0b",linestyle="--")
    ax.set_title(task["task"].replace("_"," "));ax.set_ylabel("Bookings" if task["target"]=="booking_entries" else "Team-slot hours")
    ax.legend();ax.grid(axis="y",alpha=.2)
plt.tight_layout();plt.show()'''),
      ('md','''## Inputs and partitions
Activity lags use earlier weekly booking counts and appointment hours. Rolling means, variation, trend, calendar seasonality and festival inputs are defined in the source. The booking candidate also uses earlier weather. The table retains the exact input names so the reported counts are traceable.'''),
      ('code','''display(pd.read_csv(EVIDENCE / "exact_input_names.csv"))
display(pd.read_csv(EVIDENCE / "partitions_and_use.csv"))'''),
      ('md','''## Management use
Compare the forecast with staff-entered whole-week team-slot capacity and the actual advance bookings. Inspect the team/day booking heatmap, then record a scheduling decision. No model automatically cancels or assigns appointments.

Source code: `scripts/research_management_forecasts_20261021_v2.py` builds time-safe matrices and the historical comparison. `scripts/planning_engine.py` and `scripts/cp2_planning_job.py` implement the frozen weekly protocol. The live first origin is 26 October; this document does not claim the first natural scheduled run has occurred.''')]))
    books.append(notebook('07_Model_Experiments','Model Experiments',[
      ('md','''## Historical studies
The following is the saved study summary as of 18 October. Results use different targets, periods, sample sizes and selection procedures. A higher accuracy in a different population is not automatically a better model for the original question. Full declared input lists are retained in `evidence/historical_input_lists.csv`.'''),
      ('code','''studies=pd.read_csv(EVIDENCE/"historical_studies.csv")
for section, group in studies.groupby("Section", sort=False):
    print(section)
    display(group.drop(columns=["Source"]).reset_index(drop=True))'''),
      ('md','''## Expanded management search · 21 October
This later search includes return, repurchase and enquiry targets as well as weekly planning. It is separate from the earlier study table. New classifiers did not qualify for replacement; the two planning candidates met exploratory historical gates only.'''),
      ('code','''classification=pd.read_csv(EVIDENCE/"classification_results.csv")
display(classification)
display(pd.read_csv(EVIDENCE/"dosm_results.csv"))'''),
      ('md','''## Traceability
`source_manifest.json` records original file paths and hashes. Dates in folder names identify when a study was produced; they are not proof it is the active model. The active pest-model pointer is `config/cp2_model_current.json`; the planning protocol is `config/cp2_planning_v1.json`.

Full per-candidate register: `outputs/model_validation/20261018_model_register/All_Saved_Results.csv`. Full study reports and their notebooks remain at the indexed original paths for reproducibility. Nothing in this chapter is a new independent final evaluation.''')]))

    if (calibration_study/'results.json').exists():
        books.append(notebook('08_Probability_Calibration','Probability Calibration',[
          ('md','''## Question
Can recalibrating the existing main-model probabilities and choosing a validation threshold improve useful predictions? This experiment changes neither the forest's inputs nor its weights.

Five methods were declared: raw probabilities, sigmoid, logit, beta and isotonic calibration. Calibration fitting uses only earlier matured outcomes and excludes assessment property groups. Q3 selects the method and threshold; Q4 is reported afterwards. These historical periods were examined previously, so this is exploratory evidence, not a new untouched test.'''),
          ('code','''result=read_json("probability_calibration_results.json")
display(pd.DataFrame([{"Role":"Calibration fit before July 2025","Services":result["calibration_training_services"]},
                      {"Role":"Q3 method/threshold validation","Services":result["validation_services"]},
                      {"Role":"Calibration refit before October 2025","Services":result["assessment_calibration_training_services"]},
                      {"Role":"Q4 historical assessment","Services":result["assessment_services"]}]))
display(pd.read_csv(EVIDENCE/"probability_calibration_validation.csv").round(4))'''),
          ('md','''## Historical assessment
The raw-score reference and calibration candidate use the same 410 service windows and 81 recorded positives. Both thresholds were chosen using Q3 rather than Q4. This is a different population and assessment from the original 100-service result; the percentages must not be mixed.'''),
          ('code','''comparison=pd.read_csv(EVIDENCE/"probability_calibration_assessment.csv")
display(comparison[["Configuration","services","positive_windows","accuracy","precision","recall","brier","TP","FP","FN","TN"]].round(4))
fig,axes=plt.subplots(1,2,figsize=(10,4))
comparison["Label"]=["Raw reference","Logit calibration"]
comparison.set_index("Label")[["accuracy","precision","recall"]].T.plot.bar(ax=axes[0],color=["#64748b","#2563eb"],rot=0)
axes[0].set_ylim(0,1);axes[0].set_ylabel("Fraction");axes[0].set_title("Same historical assessment")
comparison.set_index("Configuration")["brier"].plot.bar(ax=axes[1],color=["#64748b","#2563eb"],rot=0)
axes[1].set_ylabel("Probability error · lower is better");axes[1].set_title("Brier score")
axes[1].set_xticklabels(["Raw reference","Calibrated"])
plt.tight_layout();plt.show()
print("Passed the declared exploratory gate:",result["passed_exploratory_gate"])
print("Deployed:",result["deployed"])'''),
          ('md','''## Decision
Logit calibration reduced probability error, but its validation-selected threshold generated more false alerts and lower assessment precision and accuracy. It did not pass the declared gate and was not deployed. Better probability calibration alone does not establish a better yes/no decision rule.

Implementation: `scripts/test_return_probability_calibration.py`. Original protocol, source hash and numerical results: `outputs/model_validation/20261028_probability_calibration`. Frozen model weights and the future collection protocol remain unchanged.''')]))
    purchase_result=ROOT/'outputs/model_validation/20261030_programme_end_purchase/results.json'
    if purchase_result.exists():
        from scripts.research_programme_end_purchase import make_notebook
        books.append(make_notebook())
    commercial_result=ROOT/'outputs/model_validation/20261030_commercial_quote/results.json'
    if commercial_result.exists():
        from scripts.research_commercial_quote import make_notebook
        books.append(make_notebook())
    # Inventory source code/configuration only: credentials and raw records are excluded.
    records=[]
    allowed={'.py','.sql','.md','.json','.yaml','.yml','.ps1','.csv','.ipynb','.html','.css','.js','.txt'}
    active={'cp2_reporting_release.py','cp2_cloud_collector.py','cp2_planning_job.py','planning_engine.py','cp2_geocoding.py','cp2_model.py','callback_live_features.py','callback_live_weather.py','service_programme_policy.py','calendar_appointment_policy.py','sales_payment_rules.py'}
    retired={'cp2_pipeline_tick.py','install_cp2_local_runner.ps1'}
    for top in ['scripts','dbt/models','dbt/macros','dbt/tests','dbt/seeds','config','infra','.github','webapp','tests','templates','planning','notebooks','project_guide','archive']:
        for p in sorted((ROOT/top).rglob('*')):
            if not p.is_file() or p.suffix not in allowed or '__pycache__' in p.parts: continue
            rel=p.relative_to(ROOT)
            if 'evidence' in p.parts or p.suffix=='.html' and top=='notebooks': continue
            title,purpose=describe(p)
            role='Source / configuration; consult guide before execution'
            if rel.as_posix().startswith('archive'): role='Retired; do not execute as a current workflow'
            elif rel.as_posix().startswith('notebooks'): role='Project reading'
            elif rel.as_posix().startswith('scripts/') and p.name in active: role='Active runtime / current entry point'
            elif rel.as_posix().startswith('scripts/') and p.name in retired: role='Retired local collector; historical reference'
            elif rel.as_posix().startswith('scripts/') and category(rel)=='Prediction and evaluation': role='Research or evaluation utility; not automatically an active model'
            elif rel.as_posix().startswith('planning/archive'): role='Historical record'
            records.append({'Path':rel.as_posix(),'Name':title,'Purpose':purpose,'Area':category(rel),'Role':role})
    for p in ROOT.iterdir():
        if p.is_file() and (p.suffix in allowed or p.name.startswith('Dockerfile')) and not p.name.startswith('.'):
            title,purpose=describe(p);records.append({'Path':p.name,'Name':title,'Purpose':purpose,'Area':category(Path(p.name)),'Role':'Project entry/configuration'})
    frame=pd.DataFrame(records).drop_duplicates('Path')
    guide=ROOT/'project_guide';guide.mkdir(exist_ok=True)
    frame.to_csv(guide/'File_Catalogue.csv',index=False)
    evidence_files=[]
    for base in ['outputs/model_validation','outputs/cp2-v2','outputs/supervisor_model_review','outputs/reporting_release','outputs/project_audit']:
        for p in sorted((ROOT/base).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts: continue
            relative=p.relative_to(ROOT)
            evidence_files.append({'Path':relative.as_posix(),'Name':p.stem.replace('_',' ').replace('-',' '),
                                   'Study or run':relative.parent.as_posix(),'Type':p.suffix.lstrip('.'),
                                   'Bytes':p.stat().st_size,'Role':'Dated evidence; preserve original path and protocol; not automatically current'})
    pd.DataFrame(evidence_files).to_csv(guide/'Evidence_Catalogue.csv',index=False)
    # HTML catalogue uses technical paths as links and readable titles for navigation.
    table=''.join('<tr>'+''.join('<td>'+ (f'<a href="{html.escape(r["Path"])}">{html.escape(str(v))}</a>' if k=='Path' else html.escape(str(v)))+'</td>' for k,v in r.items())+'</tr>' for r in frame.to_dict('records'))
    nav=''.join(f'<a class="book" href="notebooks/{b["file"].replace(".ipynb",".html")}"><strong>{html.escape(b["title"])}</strong><small>Read chapter · <span>{b["file"]}</span></small></a>' for b in books)
    (ROOT/'FILE_GUIDE.html').write_text('''<!doctype html><html><head><meta charset="utf-8"><title>Nomobug Project Files</title><style>body{font:15px/1.6 Arial;color:#1e293b;background:#f5f7fb;margin:0}main{max-width:1200px;margin:40px auto;padding:24px}h1{font-size:32px}h2{margin-top:36px}.books{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.book{display:block;background:white;padding:16px;border:1px solid #dbe2ed;border-radius:8px;text-decoration:none;color:#172554}.book small{display:block;color:#64748b}input{padding:12px;width:95%;border:1px solid #cbd5e1;border-radius:6px;margin:10px 0}table{border-collapse:collapse;background:white;width:100%;font-size:12px}th,td{padding:10px;border-bottom:1px solid #e2e8f0;text-align:left;overflow-wrap:anywhere}th{background:#eaf0fb}a{color:#1d4ed8}.sub{color:#64748b}</style></head><body><main><h1>Nomobug Project Files</h1><p>Data, prediction models, application and cloud automation · 30 October 2026</p><h2>Project notebooks</h2><p>Read in order. Each chapter has an executed Jupyter notebook and an HTML reading copy. The notebooks contain aggregate evidence, not customer records.</p><div class="books">'''+nav+'''</div><p><a href="project_guide/Project_Structure.md">Folder guide</a> · <a href="project_guide/BigQuery_Catalogue.csv">BigQuery catalogue</a> · <a href="project_guide/File_Catalogue.csv">Download file catalogue</a></p><h2>File catalogue</h2><p>Working scripts remain at their original import paths. Readable names identify their purpose; “source/configuration” is not permission to run every script.</p><input id="find" placeholder="Search by purpose, file, or project area" aria-label="Search files"><table><thead><tr>'''+''.join('<th>'+c+'</th>' for c in frame.columns)+'''</tr></thead><tbody>'''+table+'''</tbody></table></main><script>document.querySelector('#find').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script></body></html>''',encoding='utf-8')
    entry=ROOT/'FILE_GUIDE.html'
    entry.write_text(entry.read_text(encoding='utf-8').replace('Download file catalogue</a>','Download file catalogue</a> · <a href="project_guide/Evidence_Catalogue.csv">Dated evidence catalogue</a> · <a href="project_guide/Cloud_Resources.md">Cloud resources</a>'),encoding='utf-8')
    (OUT/'README.md').write_text('# Project notebooks\n\nOpen 00_Project_Overview.ipynb first, then chapters 01–10 in order. HTML copies provide the same saved outputs without Jupyter.\n\nRun from the project root with `.venv/Scripts/python.exe -m scripts.build_project_notebooks` to regenerate from pinned evidence. Individual notebooks run from this folder or the project root. Dependencies: pandas, matplotlib, scikit-learn and Jupyter/nbformat. No Google credentials or raw customer data are included in this folder.\n\nThese notebooks replay recorded aggregate evidence. Full training and source-cleaning implementations remain in scripts and dbt, with exact paths in each chapter. Chapters 09 and 10 can refit their already selected models when private rows exist; it does not repeat the model search. No notebook build publishes models.\n',encoding='utf-8')
    for rel,before in protected_before.items(): assert sha(ROOT/rel)==before,rel
    write_json(AUDIT/'notebook_acceptance.json',{'built_utc':datetime.now(timezone.utc).isoformat(),'notebooks':books,'source_files':len(sources),'catalogue_files':len(frame),'protected_unchanged':protected_before,'execution':'All code cells executed sequentially; saved outputs retained','live_queries_in_notebooks':False})
    destination=ROOT/'outputs/project_notebooks';destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination/'Nomobug_Project_Notebooks.zip','w',zipfile.ZIP_DEFLATED) as z:
        share_files=[OUT/b['file'] for b in books]+[OUT/b['file'].replace('.ipynb','.html') for b in books]+[OUT/'README.md']
        share_files += [p for p in DATA.rglob('*') if p.is_file()]
        for p in sorted(share_files):
            z.write(p,Path('notebooks')/p.relative_to(OUT))
    # Keep the current file navigation after a notebook rebuild. This does not
    # remove caches or execute any further notebooks.
    from scripts.refresh_project_file_guide import main as refresh_file_guide
    refresh_file_guide()
    print(json.dumps({'notebooks':len(books),'file_catalogue':len(frame),'share_zip':str(destination/'Nomobug_Project_Notebooks.zip')}))


if __name__=='__main__':main()
