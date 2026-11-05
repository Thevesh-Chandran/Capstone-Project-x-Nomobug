# Return-prediction alternatives — 17 October 2026

Completed the bounded historical search across 7/14/30/60-day outcomes, each-paid-service and final-paid-service targets, all/residential populations, four model families and four feature sets. Added the owner-requested residential 3x third-service supplement. This is adaptive historical research, not new prospective accuracy.

Broad search: **704 fits and 192 supported candidate contracts**. Residential 3x supplement: **176 fits and 48 contracts**. Some targets/folds lacked sufficient positive outcomes and were skipped rather than assigned a misleading accuracy.

## Source and validation

The experiment uses the pinned 5,598-row archived research epoch, with 7,647 matching Calendar service facts. All source identities and all original 30-day labels reconciled before alternate outcomes were built. The recorded complete observation date is 13 September 2026. A 60-day service window therefore ends by that date; later immature anchors are excluded. This is a different source epoch from the 5,695-row prospective refit, so totals are not interchangeable.

Labels are recorded corrective/warranty Calendar visits linked to the sale, strictly after the anchor and within the selected number of days. They are neither independently confirmed biological recurrence nor formal claim-sheet submissions. One recorded visit can contribute to several earlier service windows. Final-service targets require one recorded occurrence of each paid stage 1..N. This is evidence of recorded stages, not proof every scheduled treatment was completed.

Current corrected programme links, later source revisions, and historical cancellation/source limitations are not fully regenerated into the archived epoch. Results therefore identify possible candidates for a current-source rebuild, not deployment-ready replacements.

## Fair comparison

Four chronological outer periods were declared in advance. Within each, training and a later calibration portion are separated by a full outcome-maturity gap and connected property/package groups. The evaluation period follows both. Calibration adjusts probabilities and chooses the F1 cutoff only from earlier calibration labels. Every eligible evaluation service is classified; there is no top-20% capacity quota.

Candidates below are the highest pooled historical F1 among contracts with at least three usable folds, within each target/horizon/population. Choosing winners from these inspected outcomes creates selection optimism; a new future evaluation is required. Different targets have different prevalence and business meanings, so the table is not a universal ranking of horizons.

## Leading supported alternatives

| Days | Anchor | Clients | Model / features | Evaluated | Positive windows | Recall | Precision | F1 | Accuracy / no-return baseline |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 14 | Each service | all | Extra Trees / service | 2698 | 51 | 21.6% | 10.5% | 0.141 | 95.0% / 98.1% |
| 14 | Each service | residential | Random Forest / service | 2176 | 49 | 22.4% | 10.0% | 0.138 | 93.7% / 97.7% |
| 14 | Final paid service | all | Random Forest / service | 870 | 41 | 29.3% | 9.8% | 0.146 | 83.9% / 95.3% |
| 14 | Final paid service | residential | Extra Trees / history | 720 | 40 | 62.5% | 11.3% | 0.191 | 70.6% / 94.4% |
| 30 | Each service | all | Extra Trees / environment | 3578 | 374 | 51.1% | 26.3% | 0.348 | 80.0% / 89.5% |
| 30 | Each service | residential | Extra Trees / environment | 2963 | 362 | 54.7% | 28.5% | 0.375 | 77.7% / 87.8% |
| 30 | Final paid service | all | Extra Trees / environment | 1171 | 238 | 77.7% | 28.7% | 0.420 | 56.3% / 79.7% |
| 30 | Final paid service | residential | Extra Trees / weather | 995 | 233 | 87.1% | 28.0% | 0.424 | 44.6% / 76.6% |
| 60 | Each service | all | Random Forest / environment | 3316 | 876 | 87.2% | 32.1% | 0.470 | 47.9% / 73.6% |
| 60 | Each service | residential | Gradient boosting / weather | 2795 | 856 | 90.9% | 33.0% | 0.484 | 40.8% / 69.4% |
| 60 | Final paid service | all | Logistic regression / service | 1097 | 325 | 92.0% | 38.1% | 0.539 | 53.4% / 70.4% |
| 60 | Final paid service | residential | Logistic regression / service | 937 | 319 | 92.5% | 39.4% | 0.553 | 49.1% / 66.0% |

## Residential 3x after the third paid service

This is the requested specific warranty-follow-up population. The 30-day outcome matches the stated residential 3x claim window after the actual third paid visit; no 14-day completion rule is imposed. Other horizons are research sensitivity checks, not changes to customer warranty entitlement.

| Days | Model / features | Folds | Services | Returns caught | Missed | False alarms | Recall | Precision | Accuracy / baseline |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | Insufficient supported folds | — | — | — | — | — | — | — | — |
| 14 | Random Forest / service | 3 | 627 | 23 | 17 | 247 | 57.5% | 8.5% | 57.9% / 93.6% |
| 30 | Random Forest / weather | 4 | 877 | 160 | 69 | 347 | 69.9% | 31.6% | 52.6% / 73.9% |
| 60 | Logistic regression / service | 4 | 823 | 290 | 23 | 441 | 92.7% | 39.7% | 43.6% / 62.0% |

For the 3x/30-day target, the leading searched candidate's F1 is 0.435. Predicting a return for every programme would already achieve F1 0.414; that baseline catches every positive but raises many false alarms. The searched candidate's mean probability error is 0.1999, versus 0.2001 for the earlier-data prevalence baseline. This comparison prevents a high recall alone from being mistaken for strong prediction.

## Interpretation and next step

At the declared calibration-F1 cutoffs, none of the 240 supported contracts exceeded its always-no-return accuracy baseline. This does not prove that no other cutoff can improve accuracy; the chosen cutoffs deliberately balance positive detection with false alarms. It does show that this bounded search has not established a dependable high-accuracy predictor.

A shorter horizon can increase no-return accuracy merely by making returns rarer. The 7-day service target has only 11 positive windows in the entire archived source and fails the declared fold-support rules. It is not evidence of excellent prediction.

Prefer a target that matches a real management decision. The residential 3x/30-day final-service target has the clearest connection to the stated warranty period. Its historical result must still be checked against a regenerated current-source dataset, linked upsell programmes and cancellation rules before any new candidate is frozen. Any eventual candidate needs its own declared prospective cohort. The current 30-day frozen model and all existing prediction receipts remain unchanged.

Eight focused horizon/split tests passed, including same-day exclusion, exact end-day inclusion, incomplete-window exclusion, and sale-specific return matching. Original source metadata still matched its archived pin after extraction. All frozen bundle file hashes were checked before and after both searches.

Protocol: `config/cp2_target_research_20261016.json`; supplement: `config/cp2_3x_final_target_research_20261017.json`. Full per-fold metrics and all contracts remain under `outputs/model_validation/20261016_target_research/` and `outputs/model_validation/20261016_target_research_3x/`. No private customer records are included in this report.
