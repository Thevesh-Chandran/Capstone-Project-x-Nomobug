> Archived evidence or implementation history. Its dated status and model choices are not current instructions. Start with [the current model guide](../../CP2_START_HERE.md).

# Warranty review findings — 27 September 2026

All 80 sampled Calendar entries have review labels. These findings assess label
quality, not predictive model accuracy. The sample is deliberately stratified;
its overall percentages do not estimate population-wide accuracy or recall.

| Original detection group | Reviewed | Confirmed claims | Other decisions |
| --- | ---: | ---: | --- |
| Eligible post-package sequence | 32 | 32 | 0 |
| Sequence requiring policy review | 8 | 7 | 1 non-claim consultation |
| Explicit warranty wording | 24 | 18 | 6 non-claims |
| Complimentary negatives | 8 | 5 | 3 non-claims |
| Other matched negatives | 8 | 0 | 6 non-claims, 2 unclear |

The original positive labels have sample precision 57/64 = 89.1%, with a Wilson
95% interval of 79.1–94.6%. Five of the 16 sampled negatives are actually claims.
This 31.3% diagnostic rate is not the model's false-negative rate: the negative
sample oversamples particular ambiguous categories. All 32 eligible sequence
examples were confirmed, but their 95% interval is 89.3–100%, not proof of perfect
population precision.

## Business corrections from the review

- A correctly recorded service beyond the package sequence, such as 4/3, is a
  warranty visit. Check consultation and incorrect sequence exceptions.
- WR-003: the first 1x sale followed by Upsell 2x supplies three paid services.
  Calendar descriptions can remain stale. Link the original and upsell SALES
  records before assigning package size or claiming the extra visits are warranty.
  Do not add unrelated purchases together solely because customer names match.
- WR-004 and WR-005: promised bonus sessions belong to the original service
  allowance; they are not claim-triggered warranty visits.
- WR-007 and WR-008: a 12x package may include three free GPC services, giving 15
  included sessions. Keep contractual package tier and included service count
  separate. These two reviewed events are confirmed claims, per reviewer labels;
  the 15-session allowance does not automatically explain their event sequences.
- Complimentary visits can be claims, including discretionary commercial and
  historical 1x exceptions. Recorded claim occurrence and contractual warranty
  eligibility must remain separate. Do not expand commercial warranty entitlement.
- Warranty text can describe terms or explicitly say no warranty; those mentions
  alone must not label a visit as a claim.
- Car/house completion visits and TRBS installation/retrieval are not claims.

## Remaining ambiguities and implementation status

WR-009 is marked unclear, with an instruction to exclude the old ambiguous
record. WR-010 is marked unclear although its reason says to treat it as a
non-claim. Preserve both as unresolved in this audit rather than silently
converting uncertainty to a negative training label.

The review decisions are preserved in `planning/warranty_review_decisions.csv`,
keyed by the original Calendar event identifiers. Customer titles and free-text
notes are excluded from that versioned file. The workbook is the detailed source.

This audit has not applied event overrides to live BigQuery or retrained models.
Next implementation must apply resolved decisions with provenance, handle the
two unresolved records explicitly, correct negated warranty wording and
consultation precedence, and investigate linked upsell and bonus allowances.
Rebuild targets and re-run package-group validation after those changes. Using
the reviewed events themselves as a fresh independent test would overstate
performance; retain these as regression examples and use an untouched audit
sample to validate generalized rules.
