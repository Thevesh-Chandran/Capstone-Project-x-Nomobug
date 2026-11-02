# First-service challenger: completed exploratory comparison

The 1 October comparison did **not identify a stronger replacement for v5**. The selected contract remains the v5 control. The frozen October model, threshold, bundle and collection protocol were not changed.

## What we tested

The [fixed experiment protocol](../config/cp2_first_service_challenger_v1.json) defines four ExtraTrees models and three review policies, giving twelve contracts:

- Existing v5 features and training weights.
- Fourfold or eightfold training weight for positive first-service examples.
- A reduced feature set that removes package/service stage and package history, while retaining environmental and other historical predictors.
- For each model, reserve zero, 10% or 25% of the **review budget** for the highest-scoring first services, then fill the remaining budget globally.

Every policy receives exactly `ceil(20% of services)` review slots. Ties use stable canonical key order. A challenger must improve mean first-service recall while preserving both mean overall review recall and average precision (AP) against the control. Labels do not determine which services receive review slots.

Selection used three purged chronological 2025 folds. All anchors on or after 15 August 2026 were removed before feature preparation. Selection was written to an immutable run directory before scoring the previously inspected January–14 August 2026 diagnostic. Calibration and the reporting threshold use development out-of-fold predictions only. The experiment never scored the reserved August holdout or October outcomes.

## Results and trade-off

These are unweighted means over the three development folds, not fresh independent test accuracy.

| Model / reserved share of review budget | Mean AP | Mean overall callback recall | Mean first-service callback recall |
|---|---:|---:|---:|
| v5 / 0% | 0.241 | 51.9% | 0.0% |
| v5 / 10% | 0.241 | 48.5% | 3.3% |
| v5 / 25% | 0.241 | 39.2% | 43.3% |
| First-positive weight 4 / 0% | 0.225 | 50.4% | 0.0% |
| First-positive weight 8 / 0% | 0.225 | 46.9% | 16.7% |
| Reduced stage features / 0% | 0.205 | 41.2% | 0.0% |

The 25% reservation found five of thirteen positive first-service windows across the folds, but reduced overall recall. First-service positive support was only two, one and ten windows in the respective folds, making the mean first-service metric unstable. First-service weighting and removing stage features also reduced AP. None met the declared replacement rule.

The retained control reproduced the existing exploratory diagnostic: **1,975 service windows, 179 positives; 103 positives found in 395 reviews** (57.5% recall, 26.1% precision). It found zero of eleven first-service positives. Diagnostic AUC was 0.787 and AP 0.232. These numbers describe previously inspected historical data; they do not supersede the separate 100-service August holdout or constitute a new future test.

The verified run also uses a development-selected probability threshold of 0.19 for threshold metrics. Review-budget metrics above rank scores and do not use this threshold. The first local run used a default threshold for reporting; the verified run supersedes that threshold report without changing selection or ranking.

## Reproduction and verification

Run from the repository root with a new directory under ignored `outputs/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.compare_first_service_challengers --output-dir outputs/cp2-v2/first_service_challenger_reproduction
.\.venv\Scripts\python.exe scripts/cp2_model.py verify
```

The verified private run is `outputs/cp2-v2/first_service_challenger_v1_verified/`. It preserves the protocol, timestamped selection, model artifacts, aggregate results and customer-level predictions. Only [aggregate results](../config/cp2_first_service_challenger_results_v1.json) are copied into version control. Output paths outside `outputs/` and overwriting existing runs are refused. Source and frozen-bundle hashes are checked; the bundle is checked again after the experiment. Serialized predictor-only replay matched all diagnostic probabilities within 2.3e-16. Frozen replay matched all 5,695 mature services within 3.4e-16.

Verification completed: **397 Python tests passed**, including seven focused challenger tests. Nineteen existing Rasterio deprecation warnings remain. No warehouse SQL, reporting views or deployed collector were changed in this experiment.

## What would support a real improvement

The experiment demonstrates a coverage trade-off, not evidence for changing the deployed model. Further improvement needs more accurately recorded first-service outcomes and predictors available before a prediction: infestation severity, inspection findings, treatment details and structured callback reasons, as described in the [recording guide](CP2_CALLBACK_RECORDING_GUIDE.md). Such fields should only be introduced when source-backed, sufficiently complete and validated on later untouched cases.

The current weather and waterway predictors remain in the experiment. No new flood source or invented environmental values were added. Adding more variables cannot guarantee improvement. The source retains the documented historical cancellation/title limitations of v5. Development folds and the diagnostic have already been inspected, so neither provides an independent accuracy claim for a new model. Continue the frozen October collection and build the dashboard using the existing aggregate evaluation and its limitations.
