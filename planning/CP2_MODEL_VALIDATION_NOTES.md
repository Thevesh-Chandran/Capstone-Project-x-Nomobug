# Model validation repair — 4 October 2026

The project retains two different historical populations. The warehouse research
table contains 5,598 service windows from its 27 September build. The frozen
prospective model was refitted later on 5,695 windows from a refreshed source.
These are separate recorded source epochs, not interchangeable row inventories.

## Historical source identity

Calendar row numbers are local to a snapshot. Joining the archived research table
to current Silver by row number falsely associated 5,565 anchors with a different
date and 2,219 with a non-service category. These were validation joins across
different inventories, not 2,219 newly proven bad historical labels.

The repaired dbt horizon test checks dates, maturity, resolved target/count
consistency, non-null fields and unique service identities within the dataset.
It does not join old row numbers to current Calendar views. Source qualification
remains checked separately, rather than dropping that validation requirement.

Run the independent source check from the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.audit_callback_evidence historical --output-json outputs/model_validation/new_historical_check.json
```

The recorded contract is `config/cp2_historical_callback_validation.json`. The
checker refuses changed modification times or row counts for both the 5,598-row
anchor table and its 7,647-row historical service facts. It joins the original
immutable Bronze snapshot through row, Calendar name, event ID and event date,
then recomputes the recorded callback counts from those same historical facts.
Every query has a 100 MiB billing bound. Audit output must be new and private.
If those old warehouse tables are replaced, this check stops: it must not be
redirected to current facts or described as passed. The pin is a source lineage
guard, not a cryptographic copy of every historical warehouse cell.

The first successful check validated all 5,598 anchors with zero missing or
mismatched source identities, invalid categories/horizons, changed outcome counts
or duplicate keys. It processed 2.42 MB. Evidence is preserved privately at
`outputs/project_audit/20261004/historical_callback_epoch_validation.json`.
The table creation was confirmed through BigQuery build job
`a8766d37-7629-4b8d-99d9-841796938292`; the immediately preceding Calendar view
definition was recorded by `196f1609-f0b3-47a5-a4bf-e64cbe487a60`.

This original Bronze inventory had zero anchor titles beginning CANCELLED.
That does **not** remove the separately documented nine title/status mismatches
in the later 5,695-row frozen training input. Neither population was rewritten.

## Eligibility changes after prediction

The new `eligibility-drift` audit compares immutable prediction receipts with a
later predictor or mature-label extraction at the same population, sale and
anchor-date keys. Changed receipt hashes, another bundle and duplicate identities
are rejected. Missing predictions and formerly logged services absent from the
new extraction are retained as explicit exceptions. The audit creates no scores,
backfills no missed windows, changes no labels and never reports accuracy.

```powershell
.\.venv\Scripts\python.exe -m scripts.audit_callback_evidence eligibility-drift --prediction-directory outputs/private_download/prospective_logs --candidate-input-json outputs/private_download/mature_labels/dataset_input.json --current-calendar-json outputs/private_download/calendar_private.json --output-json outputs/model_validation/new_eligibility_check.json
```

Current Calendar events can be matched through the exact event-window hash already
bound in each immutable receipt. An old appointment later marked CANCELLED means
that appointment was postponed; its active replacement remains a separate valid
appointment with its own identity and timely-score requirement. A positively
identified HOLD/placeholder remains a source exception, including where an
extracted key was accidentally retained. The audit never assumes all Sundays are
placeholders: the owner clarified that Sunday services can occur.

Moving a Calendar event to another time changes its window hash. Existing receipts
do not expose the original Calendar ID/event ID directly, so the audit reports
that change for archived-source review instead of guessing a replacement. More
detailed exception reasons may require the preserved source snapshot or the
separate exact-identity appointment-status registry. The audit now uses
`scripts.calendar_appointment_policy.is_confirmed_placeholder` for the shipped
registry, and records its hash when checking a current Calendar inventory. A
review is effective only while both the event identity and reviewed start/end
still match; moving the appointment expires it.

The older `scripts.reconcile_callback_evidence.fetch` helper is also repaired:
it now verifies the historical table epoch and retrieves anchor descriptions
through original Bronze, old Gold facts, stable event identity and date guards.
It preserves every original anchor and refuses partial source coverage.
Its formal-claim query remains separately labelled current source context; those
sheet records do not redefine the historical Calendar callback target. To replay
the original formal-claim comparison exactly, use its preserved `--evidence-json`
input, rather than implying current sheet records are an immutable historical
snapshot.

Agreement on keys alone does not prove complete Calendar coverage, timely scoring
or mature outcomes. The original one-time evaluator and declared cohort remain
unchanged and mandatory. The final evaluator now requires this audit before
creating labels or an accuracy result, and verifies source/feature receipt hashes.
The cloud collector preserves the full audit in its restricted bucket and only
aggregate counts and integrity hashes in run journals. Missing/late predictions,
changed inputs and a second evaluation are rejected in regression tests.

## Model performance remains experimental

The reproducible frozen model still has the disclosed first-service blind spot,
the five-positive historical holdout and the separate one-positive later-period
miss. Those limitations cannot honestly be fixed by renaming metrics or selecting
a winner after inspecting test outcomes. Frozen bundle, feature artifacts, weights,
thresholds and cohort protocols remain unchanged.

Verification after this repair: the focused Python tests passed, including eleven
new source-epoch and eligibility regressions. The repaired dbt horizon test
passed against the stable archived research table. Frozen replay passed all
5,695 rows with a primary maximum probability difference of 2.22e-16. These are
reproduction and integrity checks, not a new model accuracy evaluation. The
initial dbt invocation stopped because source variables were missing; a second
invocation used a reporting-candidate schema prefix that has no research dataset.
Neither was called a pass. The successful test supplied release source variables
with `release_schema_prefix` explicitly empty and wrote compiled output to a new
ignored audit directory, preserving frozen compiled artifacts.

The repaired reconciliation helper also returned all 5,598 original anchors and
reconciled every original label, including all 1,975 inspected 2026 windows. Its
two read-only queries processed 6.17 MB. The source evidence and aggregate report
are preserved under `outputs/project_audit/20261004/` in the new
`historical_callback_reconciliation_source_private.json` and
`historical_callback_reconciliation_verified/` artifacts. This remains a source
reconciliation, not a new test cohort or model performance claim.
