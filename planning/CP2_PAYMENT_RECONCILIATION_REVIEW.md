# SALES, PAYMENTS and Recurring Payments reconciliation — 4 October 2026

Read-only inspection of all populated SALES IDs and the bounded PAYMENTS/Recurring Payments tables in SESSION & PAYMENT (NMB)- CHIA. Sources were read separately during the same review, not as a transactional snapshot. No cells were edited, payment entries fabricated or receipts inferred.

## Findings

| Check | Observed result |
|---|---|
| SALES identified rows | 2,473 unique sale IDs |
| PAYMENTS nonblank rows | 3,243, including placeholders/review rows |
| Recurring Payments customer rows | 174 |
| Recurring vs SALES paid/balance fields | All 174 match |
| Explicit recurring arrangements | All 30 are included in the recurring tab |
| Explicit recurring arrangements with positive paid amounts in SALES | 25 |
| Of those, arrangements whose PAYMENTS total differs | 11: eight without a linked entry and three with different amounts |
| Latest payment date on or before the review date | 1 October 2026 |
| Future-dated PAYMENTS entries | Three dated 31 December 2026; source rows 2137–2139 |
| PAYMENTS date cells | 3,238 serial dates, three text dates and two blanks |
| PAYMENTS reference categories | 3,232 single, seven combined, two unrecognized and two blank |
| September–4 October SALES with positive recorded paid amounts, eligible for direct comparison | 78 |
| Recent eligible sales without a single-reference PAYMENTS entry | 35 |
| Recent eligible sales with an entry but a different amount | Three |

The recurring tab is an automatic positive-balance copy of SALES. Matching it to SALES does not independently verify payment receipt or the completeness of PAYMENTS. PAYMENTS is receiving entries, but does not consistently reconcile with SALES; it cannot alone establish which instalments are unpaid.

## Comparison method

The SALES reference is a sale/package ID, not a persistent person ID. Compare Deposit Paid plus Balance Paid with the sum of numeric PAYMENTS amounts linked by a valid single sale reference. Blank SALES deposit/balance cells are treated as zero only to mirror its spreadsheet balance formula; malformed populated amounts remain unresolved. Reference fields are parsed as whole fields with case/whitespace normalization, never matched by customer names, phone numbers or partial IDs. Combined references are retained for review without duplicating or splitting their amounts. Underlying numeric Sheets date serials supply payment years; future-dated entries are excluded from the paid-total comparison and flagged. Undated numeric entries remain available for amount reconciliation and separately require date review.

Across all historical SALES rows, 2,422 positive-recorded-paid cases were eligible for this direct comparison: 1,667 matched within RM0.01, 498 had no valid single-reference PAYMENTS entry, and 257 had a different amount. Thirteen other SALES records were excluded because of malformed paid amounts or combined-reference/amount ambiguity. These are reconciliation exceptions, not 755 proven missing payments. Legacy capture coverage, payment corrections, deposits recorded elsewhere and legitimate differences in recording scope can explain exceptions; bank receipts or owner confirmation are required to resolve them.

## Operational consequence

The earlier tracker checks validated transformation logic and preserved payment totals; they did not establish complete company bookkeeping. Recorded PAYMENTS dates and amounts remain useful, but missing entries must not be labelled unpaid. Use a reconciliation queue showing both SALES paid amounts and PAYMENTS totals before assigning instalment status or reminders. Obtain source-backed dates/receipts for missing or conflicting entries; do not backfill transactions from SALES totals alone. Keep custom contractual schedules separate from the sheet's provisional generated dates.

The private exception list, live evidence and reproducible notebook are under the dated local payment_reconciliation output directory. They are not approved public dashboard sources. The existing tracker remains a preview, and reminders remain disabled.
