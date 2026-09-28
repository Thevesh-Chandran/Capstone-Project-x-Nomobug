> Archived evidence or implementation history. Its dated status and model choices are not current instructions. Start with [the current model guide](../../CP2_START_HERE.md).

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

The workbook includes original Calendar titles, which may contain customer
details, and must be kept private. Click the linked event title in Review column G
to open the original entry while signed into an account with access to that team
calendar. The event date and team calendar provide fallback navigation.

## Required human fields

Each row requires a review label, confidence, and, for errors or uncertainty, an
error reason and short note. The allowed labels are `Confirmed warranty claim`,
`Not a warranty claim`, and `Unclear`.

Because sampling is stratified, raw workbook percentages must not be treated as
population accuracy. After review, results must be reported separately by
detection reason and review stratum, with uncertainty intervals. Any systematic
false-positive or false-negative pattern must be corrected in the Calendar label
logic before model retraining.

## Analyze the completed review

After every row has a review label, run:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_warranty_label_review.py outputs\cp2-v2\CP2_Warranty_Label_Review.xlsx
```

The command writes `CP2_Warranty_Label_Review_analysis.json` beside the workbook.
It reports system-positive precision, the hard-negative positive rate, Wilson 95%
intervals, stratum-level results, unclear rows, and error-reason counts. Until all
rows are labeled, it exits with status 2 and lists the remaining review IDs.
