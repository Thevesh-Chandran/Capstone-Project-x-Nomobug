# CP2: making the project useful and defensible

Prepared 11 October 2026 from the saved model evaluation, declared protocols and current project scope. This is a recommendation and implementation guide, not evidence that the dashboard or future test is complete. No model, thresholds, cohort rules or cloud resources were changed for this review.

## Recommended contribution

Present CP2 as a pest-control decision-support system with an experimental callback-prioritisation model. The central research question is: **Can recorded service history and environmental context help staff identify services worth reviewing, given limited follow-up capacity?** Keep the existing target: a recorded corrective Calendar callback in the following 30 calendar days. This does not establish biological pest recurrence or treatment failure.

The existing scope already includes predictive modelling, operational reporting, spatial analysis and reliability evaluation. Preserve those objectives. This document does not claim that a changed presentation satisfies an unseen marking rubric.

## What the model evidence supports

The saved historical evaluation covers 100 services from 15–27 August 2026, including five callback-positive service windows. These are service windows, not necessarily five distinct customers or callback events.

| Evaluation rule | Services selected | Positive windows found | Selected without a recorded callback | Positive windows missed |
|---|---:|---:|---:|---:|
| Frozen 0.19 alert threshold | 5 | 2 | 3 | 3 |
| Predeclared highest-risk 20% | 20 | 4 | 16 | 1 |
| Corrected earlier model, highest-risk 20% | 20 | 3 | 17 | 2 |

The threshold rule has 94% accuracy versus 95% for always predicting no callback. The ranking rule has 80% callback recall and 20% precision; those are not 80% model accuracy. Randomly selecting 20 of the 100 would contain one positive window on average (20 × 5/100); this is a mathematical expectation, not a measured staff comparison. The current 4/20 result is descriptive evidence of potential concentration, not proof of future improvement or savings.

The selected model's saved prediction CSV was independently recomputed during this review: threshold TP2/FP3/FN3/TN92; top-20 TP4/FP16/FN1/TN79. The source remains private. The public-safe aggregate source is `config/warranty_new_holdout_v5.json`.

Material counter-evidence must accompany the positive result:

- Five positives are too few for a dependable performance claim. The reported paired AUC/AP intervals include no improvement over the reference.
- The separate 13-service later-period check missed its single positive at a three-review budget. It used a different historical fit and must not be pooled with the 100-service check.
- The older, already-inspected 2026 diagnostic missed all eleven first-service positives at its review budget. The 100-service holdout has no first-service positives, so it does not resolve that weakness.
- Global top-20 ranking over the historical cohort is not a tested daily queue. A real daily policy needs a declared available-at-the-time batch, capacity and tie rule before evaluation.
- Thirty-seven additional model/ensemble contracts were compared; none met the declared replacement requirements. More tuning on already-inspected evaluations does not create independent evidence.

## Work with the strongest remaining value

1. **Make the model evaluation understandable.** Add an aggregate historical review-capacity demonstration to the model page. Keep the predeclared 20% result prominent, show selected/no-callback/missed counts together, show the simple baseline and counter-evidence, and label any other capacity settings exploratory. Do not expose customer-level experimental risk scores.
2. **Demonstrate decisions supported by the operational data.** Build an evidence-backed attention summary: upcoming staff payment-reminder dates, recorded SALES balance progress, upcoming Calendar bookings, and data issues requiring review. Each item needs a date, meaning, supporting source and next action. Reminder dates and green cells do not prove payments or reminders sent; Calendar bookings do not prove completion. Confirmed warranty rules remain separate from predictive risk.
3. **Explain what environmental enrichment contributes.** Present the existing development comparisons using service/history inputs, weather and environmental context. Report negative findings too: flood additions did not qualify for the frozen model. Do not imply that adding environmental sources automatically improves predictions, or that rainfall causes callbacks. This is an evidence-based technical contribution even when a more complex input set fails to help.
4. **Measure practical usability.** Once the dashboard is complete, define short management tasks such as finding upcoming reminder workload, comparing scheduled visits across team Calendars, and interpreting the model's missed cases. Record whether the user can answer correctly and how long it takes. These measurements are pending; do not invent saved time, prevented callbacks or financial returns.
5. **Preserve the future test.** Use the unchanged frozen model and the latest declared 10–30 October cohort. Earliest full evaluation is 30 November, subject to complete timely predictions and complete outcomes. This review did not check the live collector and does not assert current coverage. Old missed windows remain recorded. An evaluation date cannot guarantee improved accuracy.

Prioritise dashboard correctness and these demonstrations over another open-ended model search. If the model does not outperform an appropriate comparator in the future test, report that finding and retain the useful operational system. Do not switch the target to warranty eligibility, package type or another easier quantity merely to advertise a higher accuracy.

## Suggested presentation statement

“CP2 brings service, sales, payment-reminder and environmental information into one decision-support system. It also evaluates whether machine learning can prioritise service follow-up. In a small historical test, reviewing the highest-ranked 20 of 100 services included four of five callback-positive windows. The system makes the review workload, missed cases, data limitations and future-validation status visible.”

## Evidence

- `config/warranty_new_holdout_v5.json`: historical results and preselected model provenance.
- `planning/CP2_MODEL_EXPLAINED.md`: target, predictors, separate threshold/ranking rules and interpretation.
- `planning/CP2_BROAD_MODEL_REVIEW.md`: 37-contract search, first-service weakness and separate later-period result.
- `config/cp2_october10_cohort.json`: authoritative current cohort dates and acceptance rules; older overview dates are stale.
- `planning/CP2_SCOPE_AND_DELIVERABLES.md`: existing system objectives, with later owner instructions controlling changed scope.
- `planning/CP2_DASHBOARD_HANDOFF.md`: approved aggregate reporting sources and payment interpretation; its older dates/status paragraphs are historical.
- scikit-learn evaluation guidance: https://scikit-learn.org/stable/modules/model_evaluation.html
- scikit-learn selection-bias guidance: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html
