# CP2 mixed-pest and first-service experiment

27 September 2026. **Keep v4 as the reference and freeze the focused RandomForest
candidate as an experimental challenger.** At equal review capacity it catches
eight additional callback anchors and reaches mixed-pest cases that the reference
misses. First-service callbacks remain undetected. This is promising diagnostic
evidence, not proof that the challenger is universally better or ready to deploy.

## Same target, population and review capacity

The target remains a recorded corrective Calendar callback within 30 days after
a paid service. It is not contractual entitlement, biological recurrence or
confirmed completion. Commercial clients still have no contractual warranty.
The seven sheet-date conflicts are owner-resolved using Calendar dates; none
of their labels changes in this experiment.

The frozen input contains 5,598 mature service anchors. All original 2026
package/property components are removed before earlier candidate selection,
calibration and fitting. Training uses 3,051 anchors with 290 positives and
outcomes known before 1 January 2026. Q2/Q3/Q4 2025 development folds also
purge their validation components and embargo unmatured outcomes.

The diagnostic cohort is the same **1,975 services with 179 positive anchors**.
Every model gets **395 reviews**, the highest-scored 20% of this same cohort.
This is a retrospective batch comparison, not an operational monthly quota.
Cutoff ties are retained; all five diagnostic variants have exactly 395 alerts.

## Changes tested

There are 27 new numeric variables: explicit first/final/single-service flags,
mixed-pest flag, package progress and remaining services, two smoothed strictly
prior callback-history rates, first/mixed-pest interactions with prior history
and rainfall, and seven pest-type interactions with first and final service stage.
The fixed history smoothing is (prior callbacks + 1)/(prior service events + 10).
Missing weather remains missing; no treatment or severity values are invented.
No current or future outcome is used to generate these predictors.

The focused training policy doubles sample weight only for positive anchors
that are first services or contain at least two recognized pest types. The
underlying model's class weighting is otherwise unchanged. Weights use only
training labels, never validation or diagnostic labels.

Two feature sets, two training policies and four pooled model families
(ExtraTrees, RandomForest, balanced logistic regression and balanced CatBoost)
produce **16 candidate contracts**. Separate specialists are not fitted:
earlier training contains only **12 mixed-pest positive anchors and 26
first-service positives**. Development-fold counts are even smaller.

Selection was fixed before diagnostic scoring:

- Overall candidate: highest mean 2025 fold average precision (AP), AUC tiebreak.
- Focus candidate: highest mean recall for the union of first/mixed-pest
  positives within the global top 20%, requiring no decline in mean overall
  AP or global top-20% recall against the fixed ExtraTrees control.
- The focus objective is an experimental screening rule, not an approved
  business cost function or operational warranty decision.

The overall candidate is standard-weight ExtraTrees with targeted features
(development AP 0.2377 versus control 0.2251). The focus candidate is targeted
RandomForest depth six with double positive-target weight (development AP
0.2354, mean target-union recall 21.7% versus zero for the control).

## Diagnostic results at equal capacity

| Variant | AUC | AP | All callbacks caught / 179 | Precision | Mixed-pest caught / 20 | First-service caught / 11 |
|---|---:|---:|---:|---:|---:|---:|
| ExtraTrees control | 0.7743 | 0.2483 | 100 | 25.3% | 0 | 0 |
| Overall-selected targeted ExtraTrees | 0.7860 | 0.2361 | 102 | 25.8% | 3 | 0 |
| Focus-selected targeted RandomForest | 0.7872 | 0.2427 | 108 | 27.3% | 10 | 0 |
| Same RandomForest/emphasis, original features | 0.7797 | 0.2350 | 102 | 25.8% | 11 | 0 |
| Same targeted RandomForest, standard emphasis | 0.7967 | 0.2411 | 103 | 26.1% | 4 | 0 |

The focus candidate's overall recall is **60.3% versus 55.9%**, with the same
number of reviewed services. It has 287 false alarms within that budget versus
295 for the control. Mixed-pest recall rises from zero to 50%; these 20 positives
are a subset of the 28 positives outside the cockroach-only category. The focus
candidate catches 12 of those 28. First-service and mixed-pest groups overlap;
their union has 30 positive anchors, not 31 independent outcomes.

The ablations matter: the same RandomForest/emphasis with original features
already catches 11 mixed-pest positives. Thus the mixed-pest improvement cannot
be attributed solely to new feature interactions. In the targeted RandomForest,
changing training emphasis improves mixed-pest capture from four to ten, and
overall capture from 103 to 108. The targeted features add six overall captures
against the same-family/emphasis original-feature control, but lose one mixed-pest
capture. These comparisons show tradeoffs, not a uniquely established mechanism.

AP is slightly lower for the challenger (0.2427 versus 0.2483), despite its higher
AUC and better capture at this review capacity. There is no single winner on
every performance measure. Diagnostic outcomes are never used to select a
different candidate, weighting strength, threshold or review fraction.

## Uncertainty and remaining limitations

Paired resampling uses the same connected package/property components for both
models: 300 repeats over 763 components. For focus minus control:

- Overall recall difference at the fixed budget: 95% interval approximately
  **-0.5 to +8.8 percentage points**, which includes zero.
- AP difference: **-0.0510 to +0.0305**, also including zero.
- Mixed-pest recall difference: approximately **+28.6 to +67.5 percentage points**.

These intervals describe this inspected diagnostic cohort. They do not correct
for repeated experimentation: the targeted ideas were motivated by prior 2026
error inspection, even though candidate selection and fitting use earlier data.
Small subgroup counts, source recording gaps, static snapshot availability and
multiple anchors linked to the same callback limit interpretation. First-service
zero-difference bootstrap bounds merely reflect two models making no detections;
they are not proof of zero underlying first-service risk.

Thresholds are selected only from earlier out-of-fold predictions and differ
between variants. The globally purged ExtraTrees control has a 0.17 threshold,
while the focus candidate has 0.13. These are comparison-artifact settings;
the retained v4 threshold remains 0.12. Threshold-based accuracy/recall are
preserved in the receipt but are not an equal-capacity feature comparison.

## Decision and next step

Retain the current governing v4 recommendation and save the focused candidate
for a prospective comparison on genuinely new mature services. Do not replace
the current contract or present its probabilities as validated operational risk.
Freeze model artifacts, preprocessing, review-capacity evaluation and source
versions before new outcomes arrive. Record features at prediction time and
evaluate after the 30-day windows mature.

First-service prediction is still an open limitation. Structured initial pest
severity, actual treatment, access problems and completion evidence are the
most useful next recording work; their value needs testing. The available
earlier first-service positives do not justify repeatedly tuning against the
same eleven diagnostic examples. The recording guide/template remain ready.

## Evidence and reproduction

Run `scripts/compare_callback_blind_spots.py` to reproduce the 16 development
comparisons and five saved variants. Its `--verify-model` option checks a saved
artifact in a fresh process against its frozen input and predictions. Private
predictions and artifacts are ignored by Git under
`outputs/cp2-v2/blind_spot_comparison/`.

The aggregate receipt, exact feature lists, all earlier fold scores, segment
support, selection rules, artifact hashes and paired intervals are in
`config/warranty_blind_spot_experiment_v1.json`. All **260 tests pass**. Five
artifacts each reproduce all 1,975 diagnostic probabilities within 1e-12.
No live source refresh, external data addition, Calendar/sheet edits, policy
changes or dashboard work was performed.
