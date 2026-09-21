# Warranty label manual validation

## Purpose

The predictive targets currently use recorded Calendar warranty signals. Manual
review is required to determine whether those entries represent genuine warranty
claims, ordinary services, rescheduling, complimentary non-warranty work, or
administrative records.

## Review sample

The deterministic 80-event sample contains:

- 24 system positives with explicit `WARRANTY`, `CLAIM`, or `CALLBACK` wording;
- 32 positives identified because the recorded sequence exceeds the package total;
- 8 sequence positives requiring policy review;
- 8 complimentary-event hard negatives;
- 8 other matched-event hard negatives.

The workbook excludes raw names, phone numbers, email addresses and addresses.
Reviewers locate the original Calendar entry by event ID and date when more
context is needed.

## Required human fields

Each row requires a review label, confidence, and, for errors or uncertainty, an
error reason and short note. The allowed labels are `Confirmed warranty claim`,
`Not a warranty claim`, and `Unclear`.

Because sampling is stratified, raw workbook percentages must not be treated as
population accuracy. After review, results must be reported separately by
detection reason and review stratum, with uncertainty intervals. Any systematic
false-positive or false-negative pattern must be corrected in the Calendar label
logic before model retraining.
