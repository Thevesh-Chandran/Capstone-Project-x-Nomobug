# Page 11 — Recurring payments and staff reminders

Use this page to answer: **How much is recorded as paid, what balance remains, and when should staff send reminders?**

The owner builds the Looker Studio page. Both aggregate sources were published to stable Gold in release `2026100404180522111f`, with the hosted reporting image updated. Connect Looker to the approved stable sources below, not dated candidate datasets or private source tables.

## Payment progress

Source: `profound-keel-500007-s4.gold.dashboard_recurring_payment_quality` after its approved release. Population: SALES rows with explicit recurring arrangements or recurring-payment notes, including paid history. These are sale/arrangement rows, not unique customers or all company receivables. PAYMENTS is excluded from this page.

| Component | Field and aggregation | Meaning |
|---|---|---|
| Arrangement value card | SUM `recorded_contract_value_rm` | Recorded package value for included arrangements |
| Recorded paid card | SUM `sales_total_recorded_paid_rm` | SALES deposit plus cumulative Balance Paid |
| Remaining balance card | SUM `positive_recorded_remaining_balance_rm` | Positive SALES balances; not certified overdue debt |
| Arrangements card | SUM `candidate_contract_rows` | Sale/arrangement rows, including history |
| Reminders in next seven days card | SUM `contracts_with_scheduled_reminders_next_7_days` | Arrangements with a next eligible reminder date from today through today + seven days, Malaysia time |
| Payment progress by arrangement | Horizontal bars: `billing_arrangement`; SUM recorded paid and positive remaining balance | Compare payment progress across arrangements |
| Arrangement summary table | Arrangement, value, paid, remaining, arrangement count, next-seven-day count | Exact amounts and context |

Format money as RM and counts as whole numbers. Use an arrangement dropdown. This is a current snapshot: do not apply the global historical business-period control. Show `tracker_as_of_date` separately from extraction freshness. `Record Count` counts summary rows, not arrangements.

Optional recorded paid share = SUM paid / SUM arrangement value, only when value is positive and SUM `contract_value_review_rows` and SUM `recorded_paid_amount_review_rows` are zero. Otherwise show unavailable. Do not cap a result above 100% or silently exclude unknown amounts. Negative balances remain in history and are not netted against positive balances, so paid plus positive remaining may exceed arrangement value. This is recorded bookkeeping, not bank-verified settlement.

## Upcoming reminder workload

Source: `profound-keel-500007-s4.gold.dashboard_recurring_reminder_schedule` after its approved release.

Add a daily column chart with dimension `reminder_date`, metric SUM `scheduled_reminder_date_rows`, and breakdown `billing_arrangement`. Add an aggregate table of reminder date, arrangement and reminder count. Scope a date-range control only to these reminder components; start with today through the next 30 days. Use the arrangement filter consistently on both sources and verify that it affects both.

These are the owner's **dates to send reminders**. Do not subtract another seven-day lead time. Green only means the date has passed; it means neither paid nor reminder sent. A passed date does not prove an unsent reminder or overdue payment. No messages are sent by these sources.

Eligibility requires a positive SALES balance, unique links, valid dates, matching balance arithmetic, a future/today reminder date, and no cancellation/hold/refund note. Future workload may include several dates for the same arrangement. `scheduled_contract_rows` is distinct only within each date/arrangement row: do not sum it across dates and call it unique contracts. Use the payment-quality view for arrangement-level upcoming counts.

The source does not provide instalment amounts. Do not repeat the full remaining balance against each future reminder or assume equal quarterly payments. **Do not blend reminder rows onto financial totals:** multiple dates would multiply money amounts.

## Coverage and staff action

Add a compact table by arrangement with SUM of:

- `contracts_without_source_schedule`
- `lifecycle_review_rows`
- `specific_terms_note_rows`
- `balance_calculation_review_rows`
- `reminder_schedule_review_rows`

These flags overlap; do not add them into one affected-arrangement count. Management can assign missing schedules and conflicting source notes for correction. The client-by-client list remains in the private tracker. Keep customer names, IDs, phone numbers, email, exact addresses and individual model scores out of this management page.

## Acceptance before sharing

Reconcile cards against the same released source, test one arrangement and reset to All, and reconcile the reminder chart for its exact date window. Verify source freshness, approved viewers, absence of private fields, and desktop/narrow rendering. No actual Looker page or permissions have been modified or checked by this handoff.
