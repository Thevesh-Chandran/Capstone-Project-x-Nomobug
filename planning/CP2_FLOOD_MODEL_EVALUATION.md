# CP2 flood context and callback model comparison

Evaluation date: 27 September 2026. The 35 candidate/locked comparisons are complete.
Flood additions did not improve development selection; the current model is retained.

## Business question and evaluation

The target remains **a recorded corrective callback within 30 days of a paid
service**. It is binary (yes/no); the model predicts a numerical probability.
This is an operational follow-up planning experiment. It does not predict
biological pest recurrence, establish treatment failure, or change warranty
eligibility. Commercial clients have no contractual warranty.

The comparison preserves all 5,598 eligible mature callback anchors. Missing
flood observations do not remove a service from the cohort. Pre-2026 purged
walk-forward folds select candidates; the previously inspected 2026 period is
a diagnostic comparison, not an untouched final test. Package/property
connected components remain disjoint across training and evaluation. All
non-flood inputs, targets, cohort keys and split hashes must agree between modes.

The bounded experiment compares five model families/configurations over three
existing feature sets, plus a prior-only baseline, with and without eight GFM
features: 32 candidate evaluations. Separate comparisons hold the baseline
winner's model and original inputs fixed while adding GFM, observation coverage
alone, or four GDACS reported-event features. Model selection uses development
average precision. Accuracy alone favours predicting no callbacks because most
services have no recorded corrective visit.

## Added sources and variables

**Copernicus Global Flood Monitoring (GFM)** supplies satellite-derived flood
pixels in an approximate circular 1 km buffer. The added inputs are maximum
observed flood fractions over the prior 7/14/30 days, distinct reliable
observation days, distinct flood-detection days, days since detected flooding,
days since a reliable observation, and maximum reliable pixel coverage. All
12 added GFM/GDACS inputs are numerical fractions, counts or days; no flood
status text or source identifier is fed into the prediction model.

Pixels marked excluded, reference water, advisory flagged or unknown are
excluded from the flood calculation. At least half of the entire buffer must
contain reliable pixels, and at least two flood ensemble members must be
available. An unusable map gives unknown exposure, not zero flooding. A valid
zero means no flood pixels were detected in the usable observations; it does
not prove the absence of flooding between observations. The buffer is regional
context, especially for geocodes with substantial location uncertainty.
[GFM product definitions](https://extwiki.eodc.eu/GFM/PUM/Products).

Only acquisition dates 1–30 local days before the service are eligible. Both
catalogue creation and processing timestamps must precede midnight on the
service date in Malaysia. Reprocessed historical maps therefore cannot supply
features to earlier predictions. Source failures are recorded separately from
absence of reliable observations. The coverage-only control contains observation
days, observation recency and maximum valid fraction; it tests whether coverage
itself is driving score changes.

**GDACS** supplies reported regional flood event polygons. Four distinct inputs
count matching reported events in the prior 7/14/30 days and record capped days
since the latest qualifying report. Only affected-area polygons qualify;
centroids and broad global geometry do not. These polygons describe reported
affected regions, not satellite-confirmed water at a customer's premises.
[Official GDACS API guide](https://www.gdacs.org/Documents/2025/GDACS_API_quickstart_v2.pdf).

The current API does not establish historical first publication of each polygon.
The exploratory join gates geometry by its latest known modification/insert
timestamp plus a conservative 24-hour delay, before the service anchor. It also
requires a prior qualifying polygon/event date. This conservative proxy can
omit genuinely available earlier information; it is not a preserved historical
feed. Zero means no matching recorded event, not proof of dry conditions.

## Extraction coverage

The final GFM catalogue contains 3,864 distinct maps over seven source tiles.
Of these, 1,482 supplied geographically and temporally relevant buffer reads.
Only 37 of 5,598 anchors (0.66%) have at least one observation meeting the
declared reliability policy. **None of those observations contains detected
flood pixels.** This does not establish that no customer experienced flooding.

| Service year | Eligible anchors | Reliable prior GFM observation | GFM flood detection | Matching prior GDACS report |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 640 | 2 | 0 | 123 |
| 2025 | 2,983 | 23 | 0 | 3 |
| 2026 | 1,975 | 12 | 0 | 0 |

Twenty-five catalogue maps lack a required quality asset. Eleven of those maps
are relevant to the eligible anchors and cannot be used; 928 anchors potentially
affected by them have explicit source-error statuses (924 without any reliable
observation and four with partial usable context). One interrupted download
succeeded on retry. No retrieval failure remains; absent quality layers were
not reconstructed or interpreted as dry pixels. Cache reuse avoided redownloading
the successful maps. The first completed pass downloaded 3,585,173,159 bytes;
the final retry downloaded 3,807,781 bytes, with earlier cached assets reused.

GDACS returned 38 Malaysian flood events and 38 affected-area polygons, including
all alert levels. An empty second API page verified query completion. All 5,598
anchors received context rows; there were no source failures. The 126 matching
anchors occur in 2024 or 2025; all four reported-event features are constant
across the 2026 diagnostic records (counts zero and censored recency 30).

There is no positive physical GFM exposure from which the model can learn a
flood-specific relationship. Differences after adding GFM columns can reflect
coverage/missingness proxies and changes in tree feature sampling. The
observation-only control is therefore necessary. GDACS may influence training
using older regional reports, but supplies no within-period exposure distinction
in the 2026 diagnostic records.

## Results and recommendation

The existing **ExtraTrees depth 6 with normalized pest, service history, weather
and mapped environmental context remains the recommended experimental model**.
It wins both the original no-flood search and the fixed-model development
comparison. Neither flood source improved the pre-2026 selection metric.
The recommended v4 callback feature contract is therefore unchanged; the
12 new flood variables remain available in the separate experimental dataset.

| Variant | Model | Development mean AP | 2026 AUC | 2026 AP | Brier | Top-20% precision | Top-20% callback recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Existing baseline | extra_trees_depth6 | 0.2380 | 0.7743 | 0.2483 | 0.0757 | 25.3% | 55.9% |
| Best GFM candidate | rf_depth3 | 0.2288 | 0.7932 | 0.2592 | 0.0752 | 25.1% | 55.3% |
| Same ExtraTrees + GFM8 | extra_trees_depth6 | 0.2207 | 0.7666 | 0.2317 | 0.0762 | 23.3% | 51.4% |
| Same ExtraTrees + coverage3 | extra_trees_depth6 | 0.2228 | 0.7705 | 0.2298 | 0.0759 | 24.8% | 54.7% |
| Same ExtraTrees + GDACS4 | extra_trees_depth6 | 0.2340 | 0.7634 | 0.2085 | 0.0764 | 22.3% | 49.2% |

All variants use the same 1,975 diagnostic services with 179 recorded callbacks.
The top-20% review group contains 395 services for every variant. AP is average
precision (higher is better); Brier measures probability error (lower is better).
The baseline captures 100 of 179 callbacks in the 395 highest-scored services.

The GFM search chooses a different model, RF depth 3. Its 2026 AUC and AP are
higher than the baseline, but development AP falls from 0.2380 to 0.2288 and
top-20% callback capture falls from 55.9% to 55.3%. This is not sufficient
evidence to replace the development-selected baseline. Holding ExtraTrees
and its original inputs fixed reduces both development and diagnostic AP
when adding either flood source.

| Variant | Development-chosen threshold | 2026 accuracy | Callback recall at threshold | Alerts |
| --- | ---: | ---: | ---: | ---: |
| Existing baseline | 0.12 | 67.9% | 72.6% | 714 |
| Best GFM candidate | 0.10 | 63.1% | 81.0% | 839 |
| Same ExtraTrees + GFM8 | 0.18 | 85.1% | 26.3% | 210 |
| Same ExtraTrees + coverage3 | 0.19 | 86.2% | 24.6% | 181 |
| Same ExtraTrees + GDACS4 | 0.18 | 85.7% | 27.4% | 201 |

Predicting no callbacks yields 90.9% accuracy and zero recall. The apparently
higher accuracy of locked flood variants accompanies far fewer alerts and
missed callbacks; it does not establish stronger operational performance.
Thresholds were chosen using development predictions, not these diagnostic
outcomes. Development calibration fitting is not independent calibration
validation.

Paired diagnostic bootstrap intervals use 500 identical resamples of the
763 package/property connected components; deltas below are first variant
minus its comparator. These exploratory intervals do not account for all
prior candidate searches or turn 2026 into an untouched test.

| Locked comparison | 95% interval for AP difference | 95% interval for AUC difference |
| --- | --- | --- |
| GFM8 minus baseline | [-0.0399, +0.0056] | [-0.0150, -0.0005] |
| Coverage3 minus baseline | [-0.0454, +0.0101] | [-0.0089, +0.0016] |
| GFM8 minus coverage3 | [-0.0275, +0.0344] | [-0.0092, +0.0016] |
| GDACS4 minus baseline | [-0.0724, -0.0102] | [-0.0196, -0.0021] |

GFM has no detected positive flood exposure anywhere in this cohort. GDACS
has no matched report in any of the three 2025 development evaluation
quarters or the 2026 diagnostic period. The present evaluation cannot
measure performance on actual flood-exposed examples. Sparse observation
availability and constant/mostly missing columns can change tree sampling
and predictions without establishing a flood-risk relationship.

Keep the baseline frozen for the next prospective evaluation on new, fully
mature services. More complete, dated local flood evidence and pre-service
infestation/property/treatment observations would make a stronger next
experiment than promoting these unsupported flood additions. No dashboard
work or change to contractual eligibility was made.

See [the source and method review](CP2_FLOOD_SOURCE_REVIEW.md) for source
limitations and [the earlier model evaluation](CP2_MODEL_IMPROVEMENT.md) for
the existing target, weather inputs and diagnostic baseline.

## Verification and replay

The scoped live warehouse build passed **27/27** (one table and 26 data tests).
The enriched table contains 5,598 rows. A full-row comparison confirms that all
original inputs and outcomes are unchanged after removing the added context
fields. Source keys, explicit coverage, prior timestamps, nested windows, fraction
bounds and unknown-versus-zero rules passed. The local suite passed **228 tests**;
its 19 warnings are Rasterio affine pending-deprecation notices.
All five saved comparison models reloaded in separate Python processes and
reproduced every one of their 1,975 diagnostic probabilities, with maximum
differences below 4e-16 and all probabilities finite within [0, 1].

```powershell
.\.venv\Scripts\python.exe scripts\fetch_flood_context.py --workers 6 --max-network-mib 4096 --upload
.\.venv\Scripts\python.exe scripts\fetch_gdacs_flood_context.py --upload
.\.venv\Scripts\python.exe scripts\build_flood_experiment.py
.\.venv\Scripts\python.exe scripts\compare_flood_models.py --reported-flood-context
.\.venv\Scripts\python.exe scripts\verify_flood_model_artifacts.py --output-dir outputs\cp2-v2\flood_model_comparison
```

Raw customer locations, source caches, fitted artifacts and prediction files
remain ignored local data. The tracked experiment contract records aggregate
results and fingerprints without customer details.

Frozen comparison input SHA256: `aa1af03186eae01c0eb65b8924a2a999af7970dbadebfddbbd71b948ce19d7e7`.
Removing only the 12 flood columns reproduces the earlier callback manifest
SHA256 exactly: `464bb51386c1bcce9744f74f61b4d0b4265be4a4631c1ede97063b62346914d9`.
The full cohort retains all 517 positive outcomes.
