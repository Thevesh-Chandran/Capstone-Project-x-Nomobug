# Source facts that remain unknown

4 October 2026. Formula/date repairs are complete for the inspected cases. The
entries below require actual source facts; they are quality exceptions, not values
that a model or formula can reconstruct. Unknown financial values are excluded
from eligible amount calculations and surfaced in management quality counts.

| Source cell | Missing fact | Current handling |
|---|---|---|
| Prospects 2026 B14966 | Actual enquiry telephone number | Wrong `=B14965+1` formula removed. Blank contact is explicitly noted; engagement and enquiry remain recorded. |
| PAYMENTS B580 | Correct linked sale identifier, if this receipt belongs to a sale | Existing phone text retained and marked unlinked. The original receipt says “Need to refund”; PAYMENT LINK row 380 records the same phone/date as CLOSED with JOHOR noted, but provides no sale ID. Do not invent a sale or count this as settled recurring payment. PAYMENTS remains excluded from recurring tracking. |

Staff should enter verified facts when available. No client reminders are sent.

## Financial cases resolved by owner confirmation — 4 October

- **CUST527 / SALES row 531:** owner requested exclusion because this sale has no
  Calendar service record. The existing disposition override already excludes
  this sale from active sale counts. SALES AA531 is now CANCELLED with the owner's
  explanation in its note. The source row and PENDING price remain for audit;
  no price or debt is invented. Other a restaurant client sales are unaffected.
- **CUST1982 / SALES row 1986:** owner confirmed Atome is the payment method and
  RM520 was paid in full. AC1986 now records RM520; the previous RM520 in AE1986
  was reclassified to zero so the receipt is counted once. X1986 is CLEAR,
  AD1986 retains Atome and the invoice, and AG1986 calculates RM0 remaining.
  Native currency formatting and the balance formula were preserved. Exact
  before/after source evidence is retained privately.

Cloud execution `cp2-reporting-daily-98l6c` published fresh release
`20261004125916e732f9`. Independent post-publication source-case checks confirmed
both corrections, the current sales-view pointer and the management privacy gate.
The changed source cells were also visually checked in native Google Sheets.

The Calendar-backed date repairs for rows 155, 507, 680, 892, 1067, 1079, 1230 and
2191 are independently documented. Row 2061 has one scheduled service: the
misplaced third-service email was preserved as an alternate-contact note, with
the third-service field cleared. All 39 inspected helper date errors resolved.

## Further evidence check — 4 October

The further read-only check searched all nine recorded operational sheet exports
and the preserved Calendar inventory by the financial cases' exact sale IDs,
customer names and the recorded Atome invoice reference. It found 18 sheet and
12 Calendar matches for the restaurant, and two sheet and three Calendar matches
for Kamilashini. These are search hits, not independent confirmations.

Before the subsequent owner confirmation, the restaurant had other sales at different premises and dates. Their prices
cannot establish the total of CUST527; the exact Commercial Clients copy remains
PENDING. Kamilashini had a RM520 payment entry and RM520 balance paid already in
SALES, but these do not establish a separate deposit amount. Using RM520 as both
deposit and balance paid would double count. PAYMENTS is not an authoritative
replacement for the owner's Sales records.

This describes the search before the owner's resolution above. Private search evidence is retained in
`outputs/project_audit/20261004/missing_fact_recheck_private.json`.
The original enquiry phone cannot be reconstructed from the erroneous adjacent-row
increment formula. No unknown value was guessed or removed from the audit.
