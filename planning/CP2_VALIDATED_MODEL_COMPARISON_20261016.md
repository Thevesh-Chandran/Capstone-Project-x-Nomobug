# Validated historical model comparison — 16 October 2026

Business objective updated: staff follow up with every customer. See [the all-service yes/no evaluation](CP2_MODEL_YES_NO_EVALUATION_20261016.md) for the primary evaluation. The top-20% comparisons below remain historical ranking research.

## Decision

No replacement qualified under the declared rule. The Extra Trees control had the strongest mean average precision and mean 20%-capacity return capture on the three 2025 model-selection folds. No model was deployed or substituted into the running prospective experiment.

## Data and checks

The pinned 27 September input contains 5,695 mature service windows and 521 positive recorded-return windows. This is an archived reproducible snapshot, not a fresh 16 October source extraction. Status review uses the archived later Calendar snapshot. Original row numbers were reconstructed from the original snapshot and its stable-identity delta; later sources were joined by Calendar ID and event ID only. All original anchor identities and dates matched. No unresolved identities, changed dates, or cancellation anchors were found by this pinned review, so no rows were excluded for those reasons.

Checks also required unique service keys, resolved binary outcomes, exact 30-day windows complete through 26 September, valid within-package paid-service numbers, and weather dates before the anchor. These checks do not prove every treatment happened, every return was recorded, or biological pest recurrence. Later business-rule/source revisions are not fully regenerated into this archived input. The older claim of nine cancelled training anchors could not be reproduced with this stable-identity match; it remains a discrepancy requiring separate provenance review, rather than nine guessed deletions.

## Evaluation design

The protocol and code hash were saved before fitting. All models used the same targeted feature contract, seed 42, at most two threads, and an exact top-20% review budget with deterministic tie-breaking. Each fold trains only on earlier records whose 30-day outcomes ended before the validation period. Connected property/package groups are disjoint within each split. Three previously inspected 2025 folds select candidates; three previously inspected 2026 folds are diagnostic only. Services on or after 15 August remain excluded from this comparison.

The difference from the older 1,978-service development comparison is deliberate: this run purges groups against each fold’s validation period, rather than first excluding every group appearing anywhere in 2026 from all 2025 development. This evaluates a different historical development design; scores must not be called a fresh improvement over the old test.

| Period | Role | Training | Validation | Positive windows |
|---|---|---:|---:|---:|
| 2025_q2 | selection | 828 | 878 | 35 |
| 2025_q3 | selection | 1,567 | 877 | 78 |
| 2025_q4 | selection | 2,434 | 723 | 116 |
| 2026_q1 | diagnostic | 3,106 | 737 | 59 |
| 2026_q2 | diagnostic | 3,726 | 846 | 85 |
| 2026_jul_aug | diagnostic | 4,624 | 392 | 35 |

Across six nonoverlapping validation periods: **4,453 services and 408 positive service windows**. These are positive service windows, not necessarily 408 unique return visits; one recorded return can contribute to multiple earlier service windows.

## Model comparison

AP is average precision, a ranking measure from 0 to 1. It is not classification accuracy. Fold means give each period equal weight; pooled counts are reported separately.

| Role | Model | Mean AP | Mean recall at 20% review | Positive windows found / total |
|---|---|---:|---:|---:|
| selection | Extra Trees | 0.247 | 50.8% | 112 / 229 |
| selection | Random Forest | 0.236 | 49.1% | 108 / 229 |
| selection | Logistic regression | 0.183 | 42.5% | 99 / 229 |
| diagnostic | Extra Trees | 0.262 | 58.0% | 103 / 179 |
| diagnostic | Random Forest | 0.256 | 58.6% | 104 / 179 |
| diagnostic | Logistic regression | 0.267 | 58.9% | 104 / 179 |

The three 2026 diagnostic periods do not justify selecting another model. Random Forest and logistic regression each find one additional positive window in pooled reviews, while performance varies by metric and period. No new hyperparameters, thresholds, or features were chosen using these diagnostics.

Raw-score accuracy at a fixed 0.5 is recorded in the private JSON for reproducibility. Those raw scores are uncalibrated and do not use the production 0.19 calibrated threshold, so their accuracy must not be presented as updated operational model accuracy. The earlier 100-service candidate holdout remains separately labelled 94% versus the 95% no-return baseline.

## Reproducibility

- Protocol: `config/cp2_validated_forward_comparison_20261016.json`
- Runner: `scripts/compare_validated_callback_splits.py`
- Aggregate results: `outputs/model_validation/20261016_validated_forward_cv/results.json`
- Comparison CSV: `outputs/model_validation/20261016_validated_forward_cv/comparison.csv`
- Customer-level prediction CSVs stay private in the ignored output directory.
- All frozen bundle files matched their before/after SHA-256 hashes.
- Focused split/model benchmark checks: 26 passed.
- Frozen predictor replay: all 5,695 rows reproduced, with maximum probability difference 3.33e-16.

```powershell
.\.venv\Scripts\python.exe -m scripts.compare_validated_callback_splits --protocol config/cp2_validated_forward_comparison_20261016.json --output-dir outputs/model_validation/new_reproduction_directory
```

Use a new output directory for reproduction. This does not create a newly untouched test. Complete the independently logged prospective evaluation after its 30-day outcomes mature.
