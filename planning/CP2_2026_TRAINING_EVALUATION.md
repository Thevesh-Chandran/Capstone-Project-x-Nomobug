# CP2: does training on 2026 records improve callback prediction?

Evaluation date: 27 September 2026. **Retain the frozen current ExtraTrees
recommendation.** Training only on early 2026 records did not establish a
reliable improvement on the later comparison cohort. The updated all-history
model captured one additional callback at the fixed review capacity, but
its overall ranking AP was lower and uncertainty is wide.

## Question and scope

The target remains a recorded corrective callback within 30 days of a paid
service: binary yes/no, predicted as a numerical probability. Contractual
warranty eligibility is unchanged, including no commercial warranty.
This compares training periods and model choices; it does not directly
measure recording quality or prove that the 2026 process caused better data.

The frozen input has 5,598 eligible anchors and ends on 14 August 2026.
The calendar-fixed final comparison is **1 July–14 August 2026**, containing
**392 services, 35 callbacks and 236 package/property connected components**.
All 2026 outcomes were previously inspected; this remains exploratory,
not an independent final test. No new operational-source sync was required.

## Training and validation

- Frozen v4 uses its original pre-2026 training, calibration and threshold.
- Updated all-history uses 4,627 mature earlier anchors with 438 callbacks.
- 2026-only uses 1,166 mature 2026 anchors with 106 callbacks.
- Both updated regimes use identical March/April/May 2026 development windows.
- Every training and calibration outcome must be known before 1 July.
  June services are excluded because their 30-day outcomes are not yet
  mature at that cutoff. Historical predictors are retained: 2026-only
  refers to training rows, not erasing known earlier customer history.
- Both updated regimes remove final-cohort package/property components before development
  selection, calibration or fitting. Each development fold also purges its
  evaluation components and requires its training outcomes before the fold.

The frozen reference preserves its original historical selection, calibration
and threshold. Its final fitted training rows are disjoint from this later
cohort, but 122 original development/OOF rows from 32 components overlap the
later cohort's components. It is therefore a frozen historical reference, not
a newly group-independent selection/calibration benchmark. Its monotonic Platt
calibration does not change AP/AUC rankings. The direct updated all-history
versus 2026-only comparison excludes final components throughout selection,
calibration and fitting and is the stronger test of the training-period question.

The fixed-model pair holds ExtraTrees depth 6 and normalized pest, history,
weather and environmental inputs unchanged. Separately, each regime tests
five model configurations over compact history, base, and base plus weather/
environment: 30 candidate contracts total, each over three folds. Selection
uses mean development average precision (AP), followed by AUC for ties.
No later-period outcome chooses a model, calibrator or threshold.

| Fold | All-history training rows / callbacks | 2026-only training rows / callbacks | Shared validation rows / callbacks |
| --- | ---: | ---: | ---: |
| March | 3,579 / 346 | 165 / 16 | 236 / 24 |
| April | 3,810 / 357 | 408 / 31 | 269 / 26 |
| May | 4,030 / 385 | 613 / 57 | 232 / 22 |

Early 2026-only fold training is especially small. Adding newer records
changes sample size, season mix and calibration as well as recording
quality; these results should not be treated as a causal quality audit.

## Later-period results

| Variant | Model / feature set | Development AP | Later AUC | Later AP | Brier |
| --- | --- | ---: | ---: | ---: | ---: |
| Frozen current model | extra_trees_depth6 / base_weather_environment | 0.2380 (old folds) | 0.8177 | 0.2954 | 0.0729 |
| Updated all-history ExtraTrees | extra_trees_depth6 / base_weather_environment | 0.2443 | 0.8099 | 0.2427 | 0.0728 |
| All-history development winner | lr_c1.0_plain / base | 0.3234 | 0.7950 | 0.2571 | 0.0730 |
| 2026-only ExtraTrees | extra_trees_depth6 / base_weather_environment | 0.2765 | 0.8104 | 0.2610 | 0.0733 |
| 2026-only development winner | catboost_depth4_plain / compact_history | 0.3104 | 0.8054 | 0.2933 | 0.0744 |

Frozen v4 development AP comes from the earlier 2025 folds and cannot be
compared directly with the new March–May development AP. Its AUC here is
0.818 rather than the previously reported full-2026 0.774 because this is
a different evaluation subset, not a newly improved model.

| Variant | Reviewed services at top 20% | Callbacks captured / 35 | False alarms | Callback recall | Precision |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen current model | 79 | 21 | 58 | 60.0% | 26.6% |
| Updated all-history ExtraTrees | 79 | 22 | 57 | 62.9% | 27.8% |
| All-history development winner | 79 | 22 | 57 | 62.9% | 27.8% |
| 2026-only ExtraTrees | 79 | 21 | 58 | 60.0% | 26.6% |
| 2026-only development winner | 79 | 20 | 59 | 57.1% | 25.3% |

The 20% review budget rounds up to 79 of 392 services (20.15%). Keeping this
capacity fixed makes false-alarm and callback-capture comparisons fair.

| Variant | Development-selected threshold | Accuracy | Callback recall | Alerts | False alarms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen current model | 0.12 | 74.7% | 68.6% | 112 | 88 |
| Updated all-history ExtraTrees | 0.17 | 80.6% | 62.9% | 85 | 63 |
| All-history development winner | 0.13 | 72.7% | 68.6% | 120 | 96 |
| 2026-only ExtraTrees | 0.15 | 82.9% | 54.3% | 70 | 51 |
| 2026-only development winner | 0.11 | 81.6% | 57.1% | 77 | 57 |

Predicting no callbacks gives 91.1% accuracy and zero recall. Higher
accuracy after 2026-only retraining accompanies fewer alerts and more
missed callbacks, so it does not establish better useful prediction.
Development calibration fitting and F1-threshold tuning are not
independent calibration validation.

## Uncertainty and recommendation

Paired percentile bootstrap intervals use 200 identical resamples of the
236 connected components, preserving the same services within each pair.
These are exploratory estimates with only 35 positive outcomes; they do
not account for all previous model searches.

| Comparison | 95% interval for AP difference | 95% interval for AUC difference |
| --- | --- | --- |
| Updated all-history ExtraTrees minus frozen current model | [-0.1481, +0.0055] | [-0.0230, +0.0053] |
| All-history development winner minus frozen current model | [-0.1305, +0.0607] | [-0.0616, +0.0114] |
| 2026-only ExtraTrees minus frozen current model | [-0.1636, +0.0876] | [-0.0426, +0.0290] |
| 2026-only development winner minus frozen current model | [-0.1172, +0.0922] | [-0.0627, +0.0485] |
| 2026-only ExtraTrees minus all-history ExtraTrees | [-0.0593, +0.1054] | [-0.0313, +0.0311] |

Neither retraining regime establishes an improvement over the frozen model.
The direct 2026-only versus all-history fixed-model AP interval spans zero.
The all-history review gain is one callback, while its ranking AP falls.
The 2026-only development-selected CatBoost is close to frozen AP but
captures one fewer callback at the fixed review budget. Keep these fitted
candidates for a prospective comparison; do not replace v4 based on this
already-inspected, small later-period sample.

The next independent evaluation needs new, fully mature services absent
from this frozen snapshot. The most useful new operational inputs remain
pre-service infestation severity/evidence, treatment and property context,
and dated callback reasons. Recording those is preferable to redefining
the target merely to obtain a higher score. Dashboard work remains deferred.

## Verification and replay

All 231 local tests passed. All five saved artifacts reproduced all 392
later-period probabilities in separate Python processes; maximum differences
were below 4e-16, and every probability was finite within [0, 1]. No warehouse
or source labels changed. Customer locations and predictions remain ignored.

Input SHA256: `464bb51386c1bcce9744f74f61b4d0b4265be4a4631c1ede97063b62346914d9`.
Shared final-cohort key SHA256: `d9d50856dd2a3edcc9b88d97a59bd05448efccc38ca91c2697adc8d314f16488`.

```powershell
.\.venv\Scripts\python.exe scripts\compare_2026_training.py
.\.venv\Scripts\python.exe -m pytest -q
```

See [the original model evaluation](CP2_MODEL_IMPROVEMENT.md) and
[the flood experiment](CP2_FLOOD_MODEL_EVALUATION.md) for prior context.
