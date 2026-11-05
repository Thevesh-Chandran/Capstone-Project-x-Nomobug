# CP2 evaluation split comparison — 16 October 2026

A new six-period, three-model comparison has now been run. See [the completed comparison](CP2_VALIDATED_MODEL_COMPARISON_20261016.md). The counts below describe the earlier stored experiment, not the newly executed folds.

## What the 100-service result means

The 100-service holdout was a dated future window. It should not be expressed as a random percentage of the later refitted training population; the later 5,695-row refit includes that period. It was a short, forward-in-time window: 15–27 August 2026. Five of those 100 services had the recorded 30-day return outcome. The candidate models were trained on 5,333 earlier services whose outcome windows had matured before that holdout began. This is why the holdout is small: the evaluation period was about two weeks, not a fixed percentage of all rows.

After that candidate evaluation, the frozen prospective bundle was refitted on 5,695 eligible historical service windows through 27 August. The 100-row result therefore describes an earlier candidate evaluation; it is not a new independent evaluation of the later all-history refit.

## Existing time-forward comparison

The saved, property-and-package-purged development comparison used three forward-in-time validation windows in 2025. For the selected Extra Trees candidate, the folds were:

| Validation period | Earlier training services | Held-out services | Recorded return cases |
| --- | ---: | ---: | ---: |
| 2025 Q2 | 808 | 796 | 31 |
| 2025 Q3 | 1,525 | 772 | 71 |
| 2025 Q4 | 2,371 | 410 | 81 |
| **Across folds** | Separate expanding fits | **1,978** | **183** |

These are three separate validation periods, not one test set. They already show why a single percentage can be misleading: time windows contain different numbers of services and different return rates. The per-fold average precision for the selected candidate was 0.111, 0.252, and 0.358, respectively; ROC AUC was 0.759, 0.796, and 0.712. Performance varied by period.

The split procedure kept connected sale-package/property groups out of both sides of a fold and removed training rows whose 30-day outcome period would cross into validation. This reduces leakage, though missing property links and historical feature-availability limits remain.

## What we should report

- Use the forward, group-aware folds to compare candidate models during development. Do not choose the split that happens to produce the highest score.
- Keep the 100-service August holdout labelled as the earlier candidate holdout, with its small count of five returns.
- Do not describe the already reviewed 2026 diagnostics as a fresh final test; they informed later model work.
- Use the separately logged prospective cohort for the final operational evaluation after every eligible prediction and its 30-day Calendar outcome are complete.

No model weights, thresholds, or frozen bundle were changed for this comparison. A bigger holdout is possible by choosing a longer historical period, but once its results are used to tune the model, it becomes development evidence rather than an untouched final test.

## Source records

- `config/warranty_new_holdout_v5.json` — 100-row August holdout and candidate metrics.
- `config/warranty_prospective_experiment_v2.json` — later frozen bundle training count and prospective protocol.
- `outputs/cp2-v2/model_corrected_v5/candidate_results.json` — saved forward-fold comparison.
- `scripts/compare_callback_candidates_v2.py` and `scripts/warranty_validation_splits.py` — split and group-purge implementation.
