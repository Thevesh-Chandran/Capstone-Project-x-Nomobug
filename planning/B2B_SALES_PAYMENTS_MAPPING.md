# B2B / Sales / Payments: live profiling checkpoint

Evidence: scripts/profile_b2b_sales_payments.py; live Google Sheets API reads,
first read started 2026-09-12T16:53:10Z. Follow-up run confirmed key coverage.
All available dates were included; this is NOT a 2026-only sales population.
No source writes, raw exports, warehouse loads or deduplication performed.

## Source and proposed grain

| Tab | Header row | API data rows | Columns | Key-present candidates | Proposed grain |
|---|---:|---:|---:|---:|---|
| B2B FOLLOW UP | 1 | 275 | 25 | 260 with phone | Opportunity/inspection follow-up; owner confirmation pending |
| SALES | 4 | 18,064 | 43 | 2,428 with Customer ID | Sale/package record; Customer ID semantics pending |
| PAYMENTS | 1 | 3,215 | 12 | 3,200 with Customer ID | Receipt/payment entry, not unique customer |

Key presence is a profiling subset, not a validated record filter. All raw rows
must remain in Bronze. Returned rows include non-record/formula content.
Locale en_US and timezone Asia/Hong_Kong were reported for both workbooks.
Do not use locale alone to infer ambiguous date ordering.

## Mapping decisions

- B2B: positions 1 Engage Date, 3 Phone No., 5 Business Name, 7 Status,
  8 Who did Site Visit, 14 Closing Date, 15 Appointment Date.
  Positions 16–22 include quotation/follow-up/duration values; do not infer
  completion from filled cells until formulas and owner meaning are verified.
- SALES: position 7 CUSTOMER ID is a STRING; 4 Closed Date; 10 No Telefon;
  13 premise type; 24 payment/cadence label; 25 pest; 26 package;
  27 contract type; 28 Total (RM); 29 deposit; 31 balance paid.
  Keep invoice positions 30 and 32 separately; both have INVOICE ID headers.
  Service dates in positions 17–21 are not authoritative: use Calendar later.
- PAYMENTS: 1 Date; 2 Customer ID STRING; 3 Amount (RM); 4 Recipient Reference;
  6 Payment Method; 7 Complete / Pending. Reference is not assumed unique.
- Preserve positional raw columns: SALES headers include literal 11 and two
  #VALUE! cells; B2B has populated blank-header positions 24–25; PAYMENTS has
  populated blank-header positions 10–12. Do not silently discard them.
- LTV excluded. Commercial/recurring derived tabs are not separate sale facts.

## Findings and risks

| Finding | Evidence | Risk / next treatment |
|---|---|---|
| Sales ID uniqueness currently holds | 2,428 rows / 2,428 trimmed nonblank IDs | Confirm whether ID identifies person or sale before defining a key |
| Payments are one-to-many | 3,200 ID-present rows / 1,915 IDs; 1,166 repeated ID groups | Aggregate payments at the intended grain before joining prices |
| Unmatched payment IDs | 13 rows / 12 IDs; 3,187 matched rows | High join risk: retain unmatched, no guessed attribution |
| Sales lacking payment match | 525 IDs | Not proof of unpaid/lost: coverage, IDs and recording need investigation |
| Repeated payment content | One exact repeated row beyond first among ID-present payments | Review receipts; never automatically delete an actual payment |
| Amount syntax exceptions | Three fail numeric parsing after comma removal | Preserve raw and flag; no financial totals until parsed correctly |
| B2B phone repetition | 260 phone-present rows / 244 trimmed phones; 12 repeated groups | Phone alone is not a unique opportunity/customer key |

Confidence is high for these observed counts, not for explanations of exceptions.
Structural grain/join risks are high priority; malformed/blank headers and amount
exceptions need mapping review before Silver. No temporal trend was evaluated.

## Owner-confirmed sales-record grain

The owner confirmed a new Customer ID is assigned when a new sales row is added,
including repeat purchases by the same person. Treat CUSTOMER ID as sales_record_id,
preserving customer_id_raw. It is NOT a person identifier. Payments link to a sale;
separate, controlled entity resolution is required to identify repeat people.
OLD CLIENT / RETURNING in Ad is a recorded returning-client signal, not a complete
history. Ad mixes campaign/channel and relationship status. Keep both dimensions.

## Exception inspection follow-up

The read-only exception script found, among the 13 previously unmatched rows:
four match after case/space removal; seven contain multiple sales IDs; one adds
a Giro annotation; one contains a phone-shaped value. These are diagnostic
categories, not approved remappings. Do not split payments equally or duplicate
the full amount across the listed sales records.

PAYMENTS amount rows 2 and 3 contain TESTING; row 2762 contains Pest Control.
Keep raw values and flag as unparseable, never convert them to zero. The latter
may be misplaced text but its cause is unconfirmed. Rows 2061 and 2066 have
identical raw payment values; retain both pending receipt review.

Returning-label checks use whole words OLD or RETURNING, never substring OLD
(which incorrectly matches B2B COLD). Mixed labels preserve original campaign text.
Strict amount parsing uses Decimal and validates thousands separators; financial
totals must expose/exclude flagged amounts explicitly, not silently.

Owner confirmed: one payment can cover separate packages/sales IDs for the same
customer. Later balance payments create additional payment rows against the same
sales ID. Neither repeated IDs nor combined references imply duplicate receipts.
Keep payment grain separate from the payment-to-sales bridge. No amount is copied
onto each link; combined per-sale allocation remains unknown.

Total (RM) is the sale/package value. The owner clarified the #VALUE! field they
meant is unpaid balance, not package value; exact position F versus AG still needs
verification before mapping either error-labelled column as balance.

The preview parser accepts whole-field CUST IDs with spaces, slash/comma-separated
references and numeric shorthand after an explicit CUST prefix. It preserves
leading zeros. Annotation/phone-like fields remain unrecognized. A normalized
reference must resolve to exactly one Sales row; collisions are ambiguous.
Raw values remain unchanged. Snapshot-based payment keys are not cross-snapshot
transaction identities; use one selected snapshot, never sum snapshot history.

Next: verify the questionable headers/formulas, then define Bronze contracts
and Silver keys. Calendars and Sales/Payments reconciliation remain necessary
before reporting confirmed wins or completed treatments.
