# Partial pest-return evaluation — 1 November 2026

Fresh Calendar and Sheets extraction succeeded. Complete Calendar outcomes through 31 October were transformed with the frozen feature contract using temporary BigQuery tables, each query capped at 100 MiB.

Fourteen matured, source-bound, timely prediction receipts match the current original appointment windows and resolved labels. There is one recorded return. Frozen threshold 0.19 produces no alerts: 13 true negatives, one false negative, no true positives or false positives. Accuracy 92.9%, always-no-return accuracy 92.9%, recall 0%, precision undefined. This is a partial logged subset, not a complete-cohort result.

Recovery-cohort original audit: 24 missed eligible predictions and 16 unresolved candidates. Fresh source review of the unresolved windows finds 10 duplicate-session cases, two package-number mismatches, one unmatched sale and three windows absent from current candidates. Later source changes do not erase original missed windows or establish what was known then. Hotel client H was previously owner-confirmed free service; that fact is retained as contextual review and is not fabricated as a missing paid sale. Other identities need case-level source evidence before changing eligibility.

No final evaluation invoked. No frozen model/protocol/threshold or immutable cloud receipts modified. No prospective backfill. Final November evaluation remains conditional on completeness and cannot make historical gaps disappear.

Evidence: `outputs/project_audit/20261101_outcome_repair/`; reproducible partial evaluator: `scripts/evaluate_matured_cp2_subset.py`; project notebook: `notebooks/05_Pest_Return_Model.ipynb`.
