# Larger shortlist comparison — 18 October 2026

Completed the requested comparison of fixed 28-input Random Forest, 39-input notes version, and original 93-input Extra Trees. Same group-disjoint historical partition: 1,506 training services, 1,177 validation, 2,075 assessment, including 184 recorded 30-day returns. Calibration and cutoffs selected on validation; artifacts and selection saved before assessment.

The original baseline was the validation AP choice. Replayed baseline metrics exactly match the earlier larger assessment. Results:

| Model | Precision | Recall | Accuracy | F1 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original 93 | 23.02% | 64.67% | 77.69% | 0.3395 | 119 | 398 | 65 |
| RF 28 | 26.36% | 52.72% | 82.75% | 0.3514 | 97 | 271 | 87 |
| RF notes 39 | 26.34% | 53.26% | 82.65% | 0.3525 | 98 | 274 | 86 |

Decision: keep original experimental reference; no clear overall replacement. RF reduces false alerts but misses more returns. Notes add little here. Original retains higher AP and lower Brier. Previously inspected historical periods, adaptive shortlist and retrospective notes limit independence; no statistical improvement claim.

3 targeted tests passed. All confusion matrices and saved artifact/protected bundle hashes verified. Original future collection/evaluation artifacts unchanged; no assertion that its current completeness flags are cleared. Shareable notebook/HTML/ZIP under `outputs/model_validation/20261018_shortlist_larger/`.
