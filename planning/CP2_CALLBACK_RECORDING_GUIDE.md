# CP2: useful structured records for the next model

This is a proposed blank recording template, not a change to the live workbook
or Calendar. Existing contractual warranty rules and reviewed package upgrades
remain authoritative. A commercial corrective return is an operational callback,
not contractual warranty eligibility.

Use `templates/cp2_callback_recording.csv` as a starting format. Link one
callback case to its base service, sale and property; retain source references
so uncertain links can be checked. Keep customer contact details in their source
systems. Do not fill unknown values with guesses.

## Ready-to-use structured evidence path — 1 October

The original combined template above remains a reference. For new collection,
use the separate service and callback templates below. They separate information
known at the paid service from information learned when a customer returns.
The offline validator and feature builder are implemented; live Sheets/Calendar
ingestion of these new records and retraining are **not** connected yet.

The earlier recorded-description audit covered 3,623 pre-2026 and 1,975 2026
anchors. It found zero structured severity fields, ten method fields in total
(eight available as of prediction time), and no recognized usable method codes.
This is the saved historical audit, not a fresh scan of today's sources. See
[the audit evidence](../config/warranty_callback_description_experiment_v1.json).
These missing details cannot be recovered reliably by guessing from a booking.

### What staff should record

1. At each paid service, record observed pest evidence and how it was counted,
   inspection time, actual treatment methods, whether treatment was completed,
   and access problems. Use `unknown` when unverified. Keep treatment plans
   distinct from treatment actually performed.
2. When a customer requests a return, record the original request time, the
   reason, scheduled return time and actual completion time separately. Keep
   paid follow-up visits, complimentary visits and corrective callbacks distinct.
3. On a correction or reschedule, append the next numbered version and retain
   every prior version. The request time is not the rescheduled visit time.

No customer names, addresses or phone numbers are needed in these templates.
Linkage columns are private keys copied from the matched source export. Staff
can use the Calendar event link/title and local date to identify the service;
the export/join step must resolve that to the canonical service reference.
Do not require staff to search Calendar by raw event ID or invent a match.

### The three files

| Blank template | Grain and responsibility |
|---|---|
| [Service observations](../templates/cp2_service_observations_v1.csv) | One inspection/service evidence record per paid service; append versions of the same `observation_id`. Staff supply observed details; source ingestion supplies availability time. |
| [Callback outcomes](../templates/cp2_callback_outcomes_v1.csv) | One return-request case; append versions of the same `callback_case_id`. Multiple cases may link to one service. These fields never enter the candidate predictor file. |
| [Prediction anchors](../templates/cp2_prediction_anchors_v1.csv) | One eligible matched paid service with its actual prediction cutoff. Populate from validated service/collector evidence, not from an approximate date. |

Every version needs its source reference and timezone-bearing timestamps, such
as `2026-10-01T10:05:00+08:00`. `observed_at` is the actual observation time,
`recorded_at` is when that version was saved, and `available_at` is the first
time that version was ingested and available to the prediction system.
`available_at` must come from the ingestion receipt; staff must not backdate it.
Recording an inspection later cannot make its details available to an earlier
prediction. This tool validates supplied receipts but cannot independently
authenticate manually entered timestamps.

### Supported values and candidate variables

| Field | Values / handling |
|---|---|
| `evidence_count` | Whole nonnegative observed count; blank/unknown stays missing. Zero means an actual count found none. A known count requires a count method and positive inspection time. |
| `evidence_count_method` | `visual_live_pest`, `trap_capture`, `other`, `unknown`. Keep methods distinct; counts from different methods are not directly comparable. |
| `inspection_minutes` | Nonnegative minutes of actual inspection; blank/unknown stays missing. This is effort, not a treatment-quality score. |
| `treatment_methods` | `gel_bait`, `spray`, `fogging`, `misting`, `trapping`, `inspection`, `other`; join multiple codes with `|`, or use `unknown` alone. Binary performed-method features are emitted only when completion is explicitly true and methods are known. |
| `treatment_completed`, `access_problem` | `true`, `false`, `unknown`. Unknown does not become false. Completion requires actual evidence, not a confirmed Calendar booking. |
| `initial_severity`, `severity_rubric_id` | Record `unknown` until an agreed assessment rubric exists. Known severity must reference a rubric. Severity is deliberately excluded from candidate features pending rubric approval and reliability review. |
| `callback_visit_reason` | `corrective_callback`, `paid_scheduled`, `complimentary_bonus`, `inspection`, `cancelled`, `unknown`. Outcome evidence only; warranty entitlement is still governed separately. |

The feature builder emits thirteen candidate fields: evidence availability,
count, inspection effort, count method, completion and access flags, plus seven
performed-method flags. `reported_pest_types` is retained as evidence but not
automatically encoded because the current model already has normalized pest
predictors. A missing observation is marked unavailable and its other fields
stay missing. Later edits are excluded from earlier predictions.

### Run the validation and preparation

Keep filled templates in ignored private `outputs/` folders. Use a new output
directory for every run; existing evidence is never overwritten:

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_service_observation_features `
  --anchors-csv outputs/new_observations/anchors.csv `
  --observations-csv outputs/new_observations/service_observations.csv `
  --outcomes-csv outputs/new_observations/callback_outcomes.csv `
  --output-dir outputs/new_observations/validated_run_01
```

The run writes `candidate_features_private.csv` and an aggregate
`quality_summary.json` containing source hashes, available/missing/late counts
and nonmissing coverage for each feature. It rejects conflicting linkage,
duplicate anchors, incomplete version histories, invalid timestamps/counts,
unproven count methods and unexpected columns. Callback records are validated
but never used to generate predictors or automatically relabel a service.
Unmatched observation services and callback cases are counted separately;
they must be resolved against source evidence before a training join.

Verification: the full Python suite passed 418 tests. All 22 focused preparation
tests passed after adding the private-output guard test. The blank-template CLI
smoke produced zero feature records, as expected, without inventing observations.

Before another model comparison, connect immutable source receipts, check real
owner examples, review missingness by first/later service and pest, and collect
enough mature positive examples to support chronological evaluation. No fixed
sample size or coverage percentage here guarantees an improvement. Declare the
challenger comparison before its untouched evaluation period. The current
frozen October experiment and contractual warranty rules remain unchanged.

## Original combined recording reference

| Field | Meaning and recording rule | Model role |
|---|---|---|
| record_id | Unique case or service evidence record | Join/audit only |
| sales_record_id, property_id | Governing sale and actual serviced property | Linkage and split grouping |
| base_service_reference | Calendar/source reference for the paid service | Join/audit only |
| base_service_date | Local Malaysia date; YYYY-MM-DD | Prediction anchor |
| base_service_status | scheduled, completed, cancelled, no_access, unknown | Use only evidence known by prediction time |
| reported_pest_types | Separate pest types; include unknown rather than inferring from client name | Candidate pre-service predictor |
| treatment_methods | Actual recorded methods, e.g. gel_bait, spray, fogging, misting, trapping, inspection, other, unknown; multiple values allowed | Candidate predictor after the base service |
| treatment_completed | true, false, unknown; booking confirmation alone is insufficient | Candidate predictor only if known at prediction time |
| access_problem | true, false, unknown; technician evidence | Candidate predictor only if known at prediction time |
| initial_severity | none, low, medium, high, unknown; requires agreed evidence-based definitions before use | Do not backfill or model subjective guesses |
| claim_request_date | Date customer actually requests a corrective service | Potential distinct future target; never a predictor of that same request |
| callback_scheduled_date | Scheduled corrective visit date; keep request date separate | Existing recorded-visit target evidence |
| callback_completed_date | Actual completed corrective visit date, where confirmed | Completion evidence; not booking-date substitution |
| callback_visit_reason | corrective_callback, paid_scheduled, complimentary_bonus, inspection, cancelled, unknown | Outcome qualification, not a pre-callback predictor |
| source_reference | Claim-sheet row and/or Calendar title/date/reference | Manual reconciliation |
| recorded_at, updated_at | Timezone-bearing timestamps; preserve versions when changing records | Historical availability and leakage checks |

Record a reschedule as a version/change to a case rather than erasing the
original request date. Do not assume a later visit fulfilled an earlier claim
solely because it belongs to the same customer. Keep package allowance changes
and their effective dates in the governing sales records, including 1x plus
Upsell 2x becoming a three-service package.

The current model predicts a recorded corrective Calendar visit within 30 days
after a paid service. A request-within-30-days target could answer a different
business question, but must be defined and tested separately once date/link
coverage is reliable. Do not change the target merely to improve its score.

For the next prospective evaluation, freeze the current model and any candidate
before scoring newly arriving services. Preserve the exact features available
at prediction time. Wait until each 30-day outcome matures, then compare recall
and precision at the same review capacity, including first-service and mixed-pest
segments. Report accuracy alongside prevalence; predicting no callback for every
service can look accurate while finding none of the callbacks.
