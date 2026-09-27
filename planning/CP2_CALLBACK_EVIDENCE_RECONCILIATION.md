# CP2 claim-date reconciliation and description-feature experiment

27 September 2026. **Keep the retained v4 model experimental.** Ten additional
structured Problem-field features were implemented and tested, but did not
establish a useful improvement at equal review capacity. No model was deployed,
no source records or reviewed labels were changed, and the dashboard remains deferred.

## Claim requests and recorded visits are different dates

The read-only source audit reconciles all **5,598 frozen service anchors and
targets**, including all 1,975 diagnostic 2026 anchors. It reads 368 linked
claim-sheet rows, preserving claim date and warranty-claim service date separately.
331 service-date fields parse fully; 37 contain unresolved or annotated text.
Extracted dates in partially parsed fields remain flagged for review.
Slash dates are interpreted day/month/year; no ambiguous source values were corrected.

The previously identified 130 negative anchors with a dated claim record
within 30 days correspond to **96 distinct claim-sheet rows**. These anchor
counts overlap and are not 130 independent claims:

- 120 have a claim-sheet service date in days 31–60 after the anchor.
- Seven have a claim-sheet service date within 30 days but no same-sale
  Calendar visit on that date in the governing linked evidence.
- 57 have at least one exact claim-service/Calendar-callback date overlap
  somewhere in the bounded following-event evidence. This is a same-sale
  date match, not independent identification of claim fulfillment.
- Two have a service-date field requiring review. None has every linked
  service-date field blank.

For the seven within-window conflicts, a broader exact normalized phone/name
search across Calendar entries within 14 days either side found no exact-date
match. Six anchors have a usable identity key; four have nearby candidates,
including two later warranty candidates at +13 and +14 days from the sheet's
service date. The other two nearby candidates are ordinary service entries.
These do not prove rescheduling, treatment completion, or linkage to that claim.
One case lacks both supported identity keys. The search is not exhaustive.

**Owner resolution, 27 September 2026:** Calendar dates govern these seven
cases because sheet dates can be inaccurate. All seven date conflicts are
closed; existing Calendar-based 30-day outcomes remain unchanged. This resolves
date authority, not treatment completion or fulfillment of a particular claim.
The decision is scoped to these exact snapshot/case fingerprints in
`config/callback_date_authority_review_v1.json`; it does not automatically close
future discrepancies or validate claim-request dates.

The seven closed cases are saved in a private CSV with Calendar title/date and a
claim-sheet service date, so they can be checked without searching by event ID:
`outputs/cp2-v2/callback_evidence_reconciliation/private_seven_date_cases_resolved.csv`.
The original review CSV remains a historical copy; it was open/locked by Excel
when the owner resolution was recorded.
The full 130-anchor reconciliation is in `private_claim_visit_review.csv` in
the same directory. Confirmed 4/3 warranty visits and reviewed upsells were retained.

## What can be recovered from existing descriptions

The parser reads only named Problem/Pest/Masalah fields for pest indicators.
It supports seven bounded English/Malay pest patterns, multiple pest types,
HTML formatting and explicit prevention mentions. Names, addresses and emails
cannot become pest indicators through this parser. A named Method/Treatment/
Kaedah field is audited separately and does not establish treatment performed.

| Source coverage | Pre-2026 | 2026 |
|---|---:|---:|
| Anchors | 3623 | 1,975 |
| Nonempty problem field | 3402 | 1,919 |
| Recognized problem pest types | 3364 | 1910 |
| Nonempty named method field | 8 | 2 |
| Recognized named method | 0 | 0 |
| Named severity field | 0 | 0 |

2026 problem-field coverage is 97.2%. Structured method and severity coverage
is insufficient to invent useful treatment predictors. Relevant notes may exist
outside the supported named fields; absence here is not proof that technicians
never recorded those details.

## Controlled model experiment

New numeric variables: seven service-description pest flags, recognized pest
count, problem-field presence and an explicit prevention flag. Existing weather,
environment, history, premise and normalized sales-pest context are retained.
Claim dates, later callback text and claim-service dates are never predictors.

Only snapshots with timezone-bearing timestamps satisfying
**created <= updated <= recorded service end** are eligible. This removes
541 of the 5,598 anchors. Both arms use the same subset. All original 2026
package/property components, including subsequently excluded edited records,
are removed from earlier data before candidate selection or calibration.
The training outcomes also must mature before 1 January 2026.

There are **2695 training anchors with 269 positives**
and **1,869 diagnostic anchors with 176 positives**. Development uses purged
Q2/Q3/Q4 2025 folds. Four model families per arm (ExtraTrees, RandomForest,
CatBoost and logistic regression) give eight candidates; selection uses mean
development AP with AUC as a tiebreak. Both select ExtraTrees depth six.
A locked same-family feature ablation reproduces the description result.

| Arm | Development AP | 2026 AUC | 2026 AP | Callbacks captured at 374 reviews | Precision |
|---|---:|---:|---:|---:|---:|
| Refitted baseline | 0.2367 | 0.7614 | 0.2286 | 94/176 | 25.1% |
| Added description fields | 0.2380 | 0.7617 | 0.2302 | 91/176 | 24.3% |

The paired 200-resample package/property-component bootstrap gives an AP
difference interval of **[-0.0146, 0.0199]** for description
minus baseline. It includes zero. Ranking gains are not established; the added
features capture three fewer callbacks at the same capacity.

Thresholds selected on development data differ (0.14 baseline,
0.11 description). Threshold-based recall/accuracy changes
therefore cannot be attributed solely to the new variables. Both arms still
miss all 28 positive other-pest anchors and all 11 positive first-service anchors
at their selected thresholds. Those segments overlap.

The original retained v4 scores capture 98/176 at the same 374-review capacity
on this subset, AP 0.2491. This is contextual only: its original development
selection was not newly globally purged against the diagnostic components.
The comparison arms are refitted experimental controls, not changes to v4's
existing 0.12 threshold.

This remains a previously inspected 2026 diagnostic cohort. Retrospective edit
metadata can bias subset selection; the gate cannot replace versioned historical
snapshots or prospective capture. Results do not establish all-customer performance,
confirmed recurrence, or completed treatment.

## Deliverables and next useful action

A blank recording template and guide are ready:
`templates/cp2_callback_recording.csv` and `planning/CP2_CALLBACK_RECORDING_GUIDE.md`.
They separate request, scheduled visit and completed visit dates; record a
structured visit reason; and identify treatment/access/severity evidence that
would be useful if captured at prediction time. The guide preserves commercial
no-warranty policy and existing residential/package-upgrade rules.

The seven date conflicts are owner-resolved using Calendar dates; no further
manual checking is required for their date authority and no labels were changed.
Use structured records for newly arriving services and preserve their historical
versions. Evaluate a frozen candidate after new 30-day outcomes mature. The
recovered description fields are available for further development work, but
are not promoted into the governing warehouse/model contract from this result.

## Verification and reproduction

All **250 tests pass**, including HTML, plural/bilingual pest parsing, claim-date
boundaries, historical timestamp checks, exact feature joins and global final-group
purging. Three saved models each reproduce all 1,869 probabilities in fresh
processes within 1e-12. No customer-level outputs are tracked by Git.

Run `scripts/reconcile_callback_evidence.py` for the bounded source read or
pass its saved `--evidence-json` for a replay. Run
`python -m scripts.trace_claim_service_dates` for the seven-case trace, also
supporting `--evidence-json`. Run `scripts/compare_callback_description_features.py`
for the comparison or pass `--replay-model` for a saved-artifact check.
The aggregate evidence, exact SQL/job receipts, hashes, feature definitions,
candidate metrics and limitations are in
`config/warranty_callback_description_experiment_v1.json`.

The source queries processed 4,887,458 bytes (anchors), 100,441 bytes (claim
records) and 4,195,103 bytes (the final seven-case trace). Optional table-usage
metadata remains unavailable under the prior 100 MiB cap; source query receipts
are retained. No external data was added and no Calendar, sheet or warehouse
records were written.
