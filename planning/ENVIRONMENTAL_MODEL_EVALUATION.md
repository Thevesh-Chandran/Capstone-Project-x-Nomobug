# Environmental factors in the warranty-risk experiment

## Decision

Do not automatically add the current static environmental feature group to
`warranty_risk_60d_v2`. Retain it as a promising challenger and for descriptive
spatial analysis. It improves average precision modestly but does not improve
mean ROC AUC, has uneven coverage, and has only three development folds.

## Factors evaluated

- elevation;
- local terrain relief within 500 metres;
- distance to and count of mapped water features within 2 kilometres;
- distance to and count of mapped forest features within 2 kilometres;
- availability/capping indicators for the environmental lookup.

The comparison uses the same regularised random forest, 60-day target, mature rows,
prediction-safe base features and three pre-2026 walk-forward folds as v2. The
script is read-only and reproducible with:

```powershell
python scripts/evaluate_warranty_environmental_factors.py
```

## Coverage

The mature 60-day cohort contains 1,354 rows. Elevation and relief are available
for all 1,354 rows, mapped-water distance for 1,136, and mapped-forest distance
for only 253. Missing values are imputed inside each training fold; they are not
filled from future outcomes.

## Results — pre-2026 selection evidence

| Feature contract | Mean ROC AUC | Mean average precision | Mean Brier score |
|---|---:|---:|---:|
| v2 base | 0.5538 | 0.3845 | 0.2303 |
| v2 plus static environment | 0.5521 | 0.3983 | 0.2301 |

The environmental group raises mean average precision by 0.0138 and improves it
in all three folds. Mean ROC AUC falls by 0.0017 and the Brier change is
negligible. This is encouraging challenger evidence, but it is too small and too
limited in independent periods to justify expanding the frozen v2 contract.

## 2026 diagnostic

On the already-inspected 405-row 2026 reporting cohort, static environment changes
ROC AUC from 0.6215 to 0.6218 and average precision from 0.4343 to 0.4378. This
period is not a pristine holdout and cannot independently approve the feature
group.

## Interpretation

These results do not show that environmental context is irrelevant to pest
activity. The available variables are coarse mapped surroundings, forest
coverage is sparse, and the target is a recorded Calendar warranty signal rather
than measured pest recurrence. The factors remain appropriate for maps,
descriptive comparisons and later testing with stronger property-condition,
drainage/flood and confirmed recurrence data.
