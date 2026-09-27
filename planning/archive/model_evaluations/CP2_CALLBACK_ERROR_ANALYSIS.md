> Archived evidence or implementation history. Its dated status and model choices are not current instructions. Start with [the current model guide](../../CP2_START_HERE.md).

# CP2 callback model error analysis

27 September 2026. Retain the frozen model as experimental. The next useful
improvement is better operational evidence and prospective testing of pest
and service-stage blind spots. More environmental variables alone do not
address the errors identified here. No labels, threshold or source records
were changed in this analysis; the dashboard remains deferred.

## What the model predicts

The binary target is a qualifying recorded corrective Calendar visit within
30 days after a paid service. The output is a numerical probability. This
does not establish biological recurrence, completed treatment, a claim request,
or contractual warranty entitlement. Commercial customers have no contractual
warranty; operational callbacks remain a separate outcome. Residential upsells
and owner-confirmed post-package warranty visits retain their reviewed meaning.

## Performance and blind spots

The previously inspected 2026 diagnostic cohort contains 1,975 service anchors,
179 positive anchors, from 2 January to 14 August. At the unchanged 0.12
threshold: 130 detected callbacks, 49 missed callbacks, 584 false alarms and
1,212 true negatives. Recall is 72.6%, precision 18.2%, accuracy 67.9%.
At the top 20% review capacity, 395 services capture 100 callbacks: recall
55.9%, precision 25.3%. These are exploratory results, not a fresh final test.

| Segment | Services | Positive anchors | Detected | Missed | False alarms |
|---|---:|---:|---:|---:|---:|
| Cockroach only | 1,380 | 151 | 130 | 21 | 577 |
| All other pest combinations | 595 | 28 | 0 | 28 | 7 |
| Ant and cockroach | 91 | 11 | 0 | 11 | 3 |
| First service | 673 | 11 | 0 | 11 | 0 |
| Middle service | 782 | 50 | 32 | 18 | 309 |
| Final service | 520 | 118 | 98 | 20 | 275 |
| Waterway feature missing | 517 | 11 | 0 | 11 | 0 |

All threshold detections are cockroach-only. Cockroach-only records also
account for 98.8% of false alarms. First services receive no alerts. Final
services have a 22.7% recorded callback rate versus 1.6% for first services.
The model may be learning booking/package patterns as well as pest risk;
this association does not show that final services cause callbacks.

The waterway-missing pattern persists within cockroach-only records: 275
services, seven positives, no alerts, versus 1,105 services, 144 positives and
707 alerts with that feature available. Geography, geocoding and other feature
differences could explain this association. All 1,975 records have the 14-day
rainfall feature, so missing rainfall does not explain this cohort's errors.

The title-derived treatment-method category is unspecified for 1,958 services
(99.1%), including every positive outcome. It cannot support useful treatment
comparisons here. Details may exist elsewhere in free text; this does not mean
technicians never recorded them. Residential records have 171 positives;
commercial records only eight, too few for reliable commercial conclusions.

Segments overlap and must not be added across dimensions. Small pest groups
are unstable. Exported Wilson intervals are descriptive anchor-level bounds
and do not account for repeated package/property dependence. First-stage
classification takes precedence for a one-service package.

## Source and target audit

Every frozen anchor key, target and 30-day callback count was reconstructed
from the governing warehouse Calendar snapshot: all 1,975 agree. This checks
implementation consistency, not the truth of unrecorded pest outcomes.

- 155 positive anchors rely solely on post-package sequence evidence. The
  owner's confirmation that 4/3 indicates warranty remains authoritative;
  these are provenance counts, not a finding that those labels are wrong.
- 16 positives include manually reviewed callback evidence; seven are missed.
  Misses therefore cannot all be dismissed as automatic-label noise.
- 130 negative anchors have a dated claim-sheet record within 30 days but no
  qualifying Calendar callback in that window. Of these, 119 have a recorded
  callback 31–60 days after the anchor. This warrants reconciling the claim
  record's date meaning and visit linkage before considering a request-date
  target. It does not prove that the later visit fulfilled that specific claim.
  74 of the 130 are model false alarms under the current Calendar target.
- There are 289 negative anchors with a recorded callback in days 31–60.
  They remain negative for the 30-day target. Follow-up is bounded by the
  source observation date; absence is not evidence of a mature 60-day negative.
- No flagged cross-property hash/distance conflict or unreviewed extra visit
  was identified within positive 30-day windows under available evidence.
  Missing identifiers/geocodes limit that check.

There are 179 distinct callback events and 244 callback-to-anchor links.
An event can label multiple earlier service anchors. The coincidental equality
of event count and positive-anchor count does not make anchor recall an
event-level recall metric or attribute a callback to one treatment.

## Recommended next work

1. Reconcile claim request dates, scheduled visit dates and completed visit
   dates using the local review queue. Preserve valid 4/3 and reviewed upsell
   cases. Add a structured corrective/scheduled/complimentary visit reason
   and pest-at-callback field. Do not automatically relabel the 130 discrepancies.
2. Capture treatment method, products/dose where applicable, initial severity,
   completion and access issues as structured fields known at prediction time.
   Verify parsing against existing records before assuming new collection is
   necessary. Keep warranty eligibility separate from operational outcomes.
3. Test pest-specific interactions and missing-location handling using earlier
   development data, then evaluate a frozen candidate on genuinely new mature
   services. Prioritize mixed-pest and first-service recall at a fixed review
   capacity. Do not tune against this already inspected 2026 cohort.
4. Retain flood/weather features only when source coverage and earlier-period
   validation support them. The completed flood and 2026 training comparisons
   did not establish a reliable replacement for the retained model.

## Reproduction and evidence

Run `scripts/analyze_callback_errors.py`. For a source-frozen replay, pass
`--evidence-json outputs/cp2-v2/callback_error_analysis/source_evidence_private.json`.
Aggregate receipt: `config/warranty_callback_error_analysis_v1.json`.
Private local queue: `outputs/cp2-v2/callback_error_analysis/private_owner_review_queue.csv`
contains 15 missed callbacks and 15 false alarms with searchable dates, Calendar
names and titles. Customer-level artifacts are ignored by Git.

The live read processed 3,415,267 bytes in job
`2cda4cf7-894d-497d-bc6c-5050ec1b4698`. Exact SQL, snapshot hashes,
segment counts and limitations are preserved in the aggregate receipt. No
Calendar, spreadsheet or warehouse records were written.

Verification: all 237 tests passed, including six new error-classification,
threshold, tied-budget, date-boundary and source-evidence tests. A replay of
the saved source evidence reproduced the aggregate results. Best-effort
30-day table-usage metadata was unavailable because its query exceeded the
100 MiB billing cap; that optional query was not retried at a higher cap.
