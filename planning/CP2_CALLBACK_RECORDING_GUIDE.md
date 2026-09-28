# CP2: useful structured records for the next model

This is a proposed blank recording template, not a change to the live workbook
or Calendar. Existing contractual warranty rules and reviewed package upgrades
remain authoritative. A commercial corrective return is an operational callback,
not contractual warranty eligibility.

Use `templates/cp2_callback_recording.csv` as a starting format. Link one
callback case to its base service, sale and property; retain source references
so uncertain links can be checked. Keep customer contact details in their source
systems. Do not fill unknown values with guesses.

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
