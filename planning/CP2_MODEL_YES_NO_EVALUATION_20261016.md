# Predicting a recorded return within 30 days — evaluation update

The subsequent [broader target and horizon comparison](CP2_TARGET_RESEARCH_20261017.md) also includes residential 3x programmes after the third paid service.

The business follows up with every customer. A top-20% staff review limit is therefore no longer the main business success measure. The main task is a yes/no prediction for every eligible service, with a probability that reflects observed return rates. Historical top-20% metrics remain archived research context.

## Method

Used the saved forward-fit scores from the 16 October comparison. Calibration and cutoffs use 1,978 earlier 2025 out-of-fold records only, excluding every connected package/property group in the 2026 diagnostic and every outcome ending on or after 1 January 2026. A positive-slope Platt calibrator adjusts scores; the cutoff maximizes F1 on that earlier calibration set, with the higher cutoff breaking ties. All 1,975 diagnostic services are evaluated; there is no staff-review quota.

F1 balances precision and recall mathematically. It is a declared research choice, not an agreed business cost for missed returns versus false alarms. These 2026 periods were previously inspected, so the results remain retrospective diagnostics. The fitted base models change between forward periods; this is not a new evaluation of the single frozen prospective bundle.

## Results

There were 179 positive service windows and 1,796 negative windows. Predicting no return for everyone gives 90.94% accuracy but catches zero returns. A positive window is not necessarily a unique return visit, because one later return may fall within several earlier service windows.

| Model | Returns caught | Returns missed | False alarms | Recall | Precision | F1 | Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|
| Extra Trees | 100 | 79 | 275 | 55.9% | 26.7% | 0.361 | 82.1% |
| Random Forest | 111 | 68 | 318 | 62.0% | 25.9% | 0.365 | 80.5% |
| Logistic regression | 81 | 98 | 205 | 45.3% | 28.3% | 0.348 | 84.7% |

Extra Trees catches 55.9% of recorded return windows, but only 26.7% of its positive predictions turn into a recorded return. Random Forest catches 11 more returns while generating 43 more false alarms. Logistic regression produces fewer false alarms while missing more returns. No model is a clear operational winner without an agreed consequence for each kind of mistake. No result justifies advertising dependable yes/no prediction.

## Probability reliability

Brier score measures probability error; lower is better. All three models improve on a constant probability estimated only from earlier calibration records. This does not prove that every risk band is well calibrated.

| Model | Brier error | Earlier-prevalence baseline |
|---|---:|---:|
| Extra Trees | 0.0742 | 0.0824 |
| Random Forest | 0.0738 | 0.0824 |
| Logistic regression | 0.0779 | 0.0824 |

Extra Trees risk bands:

| Predicted range | Services | Average prediction | Actual return rate |
|---|---:|---:|---:|
| 0%–5% | 1067 | 2.0% | 2.4% |
| 5%–10% | 261 | 8.4% | 8.8% |
| 10%–20% | 297 | 11.9% | 12.1% |
| 20%–40% | 350 | 24.6% | 26.9% |

Sparse high-risk bands carry limited evidence. Brier improvement is aggregate probability evidence, not a guarantee for individual customers.

## Project success measures

1. Recall: proportion of actual recorded returns predicted.
2. Precision: proportion of predicted returns that actually occur.
3. Missed returns and false alarms: actual counts with the service denominator.
4. Probability reliability: Brier score versus an earlier-data baseline and risk-band observed rates.
5. Accuracy and the always-no-return baseline: secondary context because returns are uncommon.

Use earlier validation data to set candidate cutoffs. Agree business trade-offs before a final operational cutoff is selected. Preserve the running prospective model, probability calibration, threshold, and cohort rules. Any new deployed candidate needs a separately declared future evaluation.

Evidence: `outputs/model_validation/20261016_validated_forward_cv/yes_no_evaluation/results.json`; runner: `scripts/evaluate_callback_yes_no.py`. Individual prediction files remain private.
