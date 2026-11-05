# Recurring payment tracking review

## Owner clarification — 4 October 2026 (current interpretation)

The owner confirms W:AG dates are **dates to send staff payment reminders**, not contractual due-date evidence. Green means only that the date has passed; it is neither payment evidence nor proof that a reminder was sent. Use SALES deposit plus cumulative Balance Paid for recorded paid progress, and the SALES remaining balance. PAYMENTS stays excluded. Do not apply a seven-day offset to reminder dates.

The corrected dated export is `outputs/recurring_payment_tracker/20261004_reminder_schedule/tracker_private.html`. Positive-balance arrangements with a valid future reminder schedule, matching balance arithmetic, unique links, and no cancellation/hold/refund flag qualify for the staff schedule filter. Zero/nonpositive balances remain in history. Elapsed reminder dates are visible but are not automatically treated as unsent or overdue. Missing schedules, lifecycle notes, and conflicting custom notes remain visible for targeted review. No messages are sent. The aggregate sources were published to stable Gold in release `2026100404180522111f`, and the hosted reporting image is updated. The private export stays outside the management dashboard.

Validation of the corrected export: all 34 balance calculations matched; 179 reminder-date cells were retained; 24 arrangements qualified for the future staff schedule filter. Six exporter tests and all five selected warehouse data checks passed against the 4 October 06:00 Malaysia release. This filter shows scheduled dates, not verified unpaid instalments or reminders actually sent.

Historical findings below are retained as an audit trail; interpretations requiring blanket due-date confirmation or a reminder lead time are superseded by this clarification.

# Recurring payment tracking review — 4 October 2026

## Current status

**Agent review completed, 4 October:** all 34 current arrangement candidates pass the recorded balance equation (package total minus SALES deposit/balance paid equals remaining balance within RM0.01). The updated `20261004_reviewed` private export shows this result per row, rather than asking the owner to inspect every row. Seven candidates have no generated schedule: two are historical zero-balance cases and five have positive recorded balances (every-four-month or after-treatment arrangements). A cancellation note remains a source clarification, not evidence that any balance should be erased. Custom service-linked terms (e.g. RESTAURANT CLIENT T) do not match a deposit-style date schedule; Pasti Ilmi's named payment months differ from its generated date months. These source discrepancies remain flagged without inventing contractual dates, amounts or paid instalments. PAYMENTS remains excluded, and this export is not a hosted release.

**Owner decision, 4 October: exclude PAYMENTS from recurring tracking.** The current tracker uses only SALES paid amounts/balances and Recurring Payments staff reminder dates. It shows deposit paid, balance paid and total recorded paid, but no actual payment dates, last-payment amount or PAYMENTS timeline. Blank SALES paid components mirror its balance formula as zero; malformed populated amounts remain unknown. Historical sections below describe the earlier PAYMENTS-based preview and audit, which are superseded for current tracking. The new validated export is `outputs/recurring_payment_tracker/archive/20261004_sales_only/tracker_private.html`; it remains a review export, not a hosted release. Individual paid instalments and actual payment dates remain unknown; these are not prerequisites for showing the owner-defined staff reminder schedule.

The raw recurring-payment source is imported into Silver and included in source freshness checks. A SALES-based register, reminder-date view and aggregate coverage view are implemented. The aggregate management sources are published in release `2026100404180522111f` and included in the hosted daily job; the individual register remains restricted. Dates are the staff reminder schedule; no additional lead time is applied. Actual payment dates and per-instalment allocations are unknown; no overdue claim or client reminder delivery is enabled. This is a separate finance/operations requirement, not a callback-model prediction.

Read-only live inspection completed at 2026-10-04T01:47:49Z of [SESSION & PAYMENT (NMB)- CHIA](https://docs.google.com/spreadsheets/d/1lTYFxkgOB0YHTpJoxZld2wrqpsRdmP7SXNHBbyFT1Bg/edit#gid=1162828142). No source cells were edited and no reminders were sent. Workbook metadata reports a last modification on 3 October; that timestamp applies to the entire workbook, not each contract.

## Verified source behaviour

- Recurring Payments!A2 uses FILTER over SALES, selecting rows with SALES!AG > 0. AG is package total minus deposit paid minus balance paid. Thus this tab is a positive recorded-balance list, not exclusively a list of subscription contracts.
- All 174 returned customer rows matched the 174 positive-balance SALES rows in the inspected bounds. No missing customer IDs or mismatches were found in billing arrangement, pest, package, contract type, total, deposit, balance paid and balance remaining. This proves consistency with SALES, not accuracy of its bookkeeping or contract terms. The newest included sales are dated 3 October.
- Billing arrangement counts: DEPOSIT 126; PENDING 15; CLEAR 3; MONTHLY 11; QUARTERLY 14; EVERY 4 MONTHS 1; AFTER EACH TREATMENT 4. All 30 rows in the latter four categories were present in both SALES and the recurring tab. They are candidate recurring arrangements, not 30 certified active contracts.
- Recurring Payments!W2 uses MAKEARRAY and EDATE with the first-session field M and arrangement N. Monthly creates 11 future dates; quarterly creates four future dates at +3, +6, +9 and +12 months; deposit repeats the first-session date in the second-payment column. Other arrangements are not handled by the formula.
- The current source therefore resolves the old question about columns W:AG: these are generated schedule dates, not payment amounts or proof of payment. They can also contain PENDING for deposit cases. Payment Type is a misleading inherited heading: some entries are payment methods or invoice references.
- Four rows have #VALUE! in the inherited, unlabelled column D. These were retained; do not turn them into dates or financial values.

Read bounds: Recurring Payments A1:AJ200 (174 customer rows ending at row 175), formulas A1:AJ5; SALES G5:G3000 and X5:AG3000 (2,473 populated IDs); PAYMENTS A1:G5000 (3,243 non-header returned rows). The relevant sheet titles and grid bounds were confirmed from live metadata before reads.

## Why reminders are not safe yet

1. **Instalment allocation is missing.** There are 21 PAYMENTS entries whose displayed reference exactly matches one of the 30 recurring-arrangement sale IDs. The source column is called Customer ID, but the project's established definition is a sale ID. Thus a valid single reference can link a recorded payment date and amount to a contract/sale. The existing payment-date sidecar preserves the underlying year, which the displayed day/month omits. Complete / Pending is unused according to the existing owner notes; its blank value is not a blocker for recorded payment history. Combined, invalid or ambiguous references still need review. A sale-linked payment does not by itself identify the specific instalment, and the generated schedule does not consume PAYMENTS.
2. **Quarterly end dates need contract confirmation.** For example, an initial date of 18 July produces future dates on 18 October, 18 January, 18 April and 18 July. That would be five payment occasions including the initial one. Confirm whether the last occasion is a renewal, an extra payment or an incorrectly generated date; YEARLY alone is insufficient to decide.
3. **Some arrangements have no schedule.** The every-four-month row and all four after-each-treatment rows have no generated payment dates. Treatment-triggered billing requires a verified billable service, not just a scheduled Calendar appointment.
4. **Cancellation needs explicit status.** Two recurring-arrangement rows contain cancellation notes but remain in the balance-based list. A cancellation annotation is a review signal; it does not establish whether any remaining debt is payable. Do not send automatic reminders from that list.
5. **The billing anchor must be confirmed.** Dates follow the editable first-session field. A rescheduled service should not silently move contractual billing dates unless the agreement requires it.
6. **Amounts and reminders are absent.** There is no authoritative amount per scheduled instalment, instalment paid/partial status, reminder date, reminder owner or reminder history. Do not divide package value by service count or infer instalment settlement from a remaining balance.

## Proposed stakeholder deliverable

Add a restricted contract-payment register with one row per contractual instalment: contract/sale reference, approved customer/site reference, arrangement, contract start/end, instalment number, confirmed due date, agreed amount, allocated recorded payment, remaining amount, payment evidence/status, and review reason. Capture explicit active/cancelled/renewed state and any custom payment agreement.

Once terms and allocations are validated, provide an upcoming-payment queue (next 7/30 days), a verified overdue queue, partial-payment and unresolved-record queues, plus reminder date, responsible staff member, last reminder and next action. Management dashboard cards can show aggregate counts/amounts; the contact list belongs in a separately approved restricted view. Reminder lead time must be agreed with the company. An actionable queue does not imply reminders have been sent.

Keep contract value, actual payment entries and generated instalment expectations at their separate grains. Do not add recurring rows as extra sales or cash receipts. Do not publish overdue amounts or activate reminders until the terms, payment allocation and cancellation examples have been checked with the owner.

## Full SALES coverage check

A second live read on 4 October compared all 2,473 populated, unique SALES IDs with the recurring tab and inspected customer-name annotations and remarks for custom payment arrangements. The live ranges extended through row 3000; the last populated sale ID was at row 2477.

- **All 30 explicitly labelled recurring arrangements are included:** 11 monthly, 14 quarterly, one every four months and four after each treatment. There were no missing labelled arrangements.
- **The tab is not the complete history of recurring arrangements.** Two additional annotations describe monthly or per-service payment arrangements, but their SALES balance is 0.00 so the FILTER excludes them: SALES row 246 (CUST242, monthly-payment annotation) and row 386 (CUST382, payment-after-each-service annotation). These are historical arrangement signals, not evidence that either contract remains active or money is owed.
- **Custom arrangements can be mislabelled.** SALES row 1573 (CUST1569) describes RM330 every two services but its arrangement field is DEPOSIT. It is included because its balance is positive; its schedule formula therefore follows the deposit branch rather than its annotated custom terms. Row 1945 (CUST1941) likewise has a three-payment annotation with DEPOSIT.
- SALES has 173 YEARLY contract rows, of which 134 are absent from the tab and all have a non-positive recorded balance. YEARLY describes the service contract and does not establish recurring billing; these are not 134 missing recurring payers. They illustrate why an annual-contract register must start from SALES rather than this filtered list.

Owner clarification on 4 October: payment counts and terms **vary by contract**. Do not impose a universal four-payment quarterly rule or delete the generated month-12 date without checking the particular agreement. Reminder lead time has not been selected. Generated schedule dates are available; approved contractual dates and paid/remaining instalment attribution need confirmation.

Conclusion: the tab contains every explicitly labelled recurring arrangement currently in SALES, but is a current positive-balance view rather than a complete recurring-contract/payment ledger. The new register starts from SALES plus PAYMENTS, retains fully recorded-paid history, and includes custom-note candidates rather than relying on the tab's filter or labels alone.

## Earlier PAYMENTS-based preview — superseded

Validated on 4 October against published release `2026100322002159290c`, whose SALES/PAYMENTS/recurring snapshots were extracted at approximately **06:00 MYT on 4 October**. The preview contains 34 candidate arrangements (30 explicit plus four additional custom-note candidates); two have a non-positive recorded balance. Five candidates contain custom-note signals in total because one also has a Quarterly label. These are sale/contract candidates, not unique people or certified active accounts.

The tracker links 30 dated positive PAYMENTS entries across 21 candidates and retains 179 nonblank generated schedule cells for review. It shows the last recorded payment date and amount, all linked payment-history entries, the SALES balance, and the next proposed source date. A missing PAYMENTS entry is not proof of nonpayment. Generated past dates are not labelled overdue. No universal quarterly payment count, instalment amount or reminder lead time was imposed.

Implemented dbt views:

| View | Grain / access |
|---|---|
| `silver.recurring_contract_candidates` | One SALES candidate row, including recorded-paid history; restricted names and source notes |
| `silver.recurring_contract_payment_history` | One payment/candidate-sale link; combined-reference money remains unallocated |
| `silver.recurring_payment_date_candidates` | One nonblank generated schedule cell; all dates marked provisional |
| `silver.recurring_contract_payment_tracker` | One SALES candidate row with payment and proposed-date summaries; restricted |
| `gold.dashboard_recurring_payment_quality` | Aggregate arrangement/coverage/review counts; no names, IDs or individual dates |

The existing daily reporting build selects these models and their dependencies through `gold` tags after the updated reporting image is deployed. This code inclusion is **not** evidence that the current cloud image or stable views already contain them. Publish through the existing candidate build, invariant/KPI checks and rollback-controlled promotion; do not manually expose the restricted Silver tracker to the aggregate report. The existing collector/model is unchanged.

The read-only preview command is:

```powershell
.\.venv\Scripts\python.exe -m scripts.preview_recurring_payment_tracker --output outputs/recurring_payment_tracker/<new-review-directory>
```

It resolves and checks the latest published release, uses year-bearing PAYMENTS date serials, compiles into an isolated output directory, applies the 100 MiB query limit, runs grain/payment-total/schema tests, and exports a private searchable HTML register plus separate CSV timelines. Previous outputs cannot be overwritten. Customer notes are HTML-escaped and spreadsheet formula-like strings are neutralized in CSV exports. Its dated HTML export does not refresh itself.

The header-only [contract schedule template](../templates/cp2_contract_payment_schedule.csv) captures agreed due dates/amounts and their confirmation evidence. It is a collection template, not a connected source; do not claim that filling it already changes the warehouse. Contract terms and payment-to-instalment assignment need a separate validated ingestion before an actionable unpaid/reminder queue can be enabled.

## Subsequent three-tab reconciliation

The [4 October payment reconciliation](CP2_PAYMENT_RECONCILIATION_REVIEW.md) found that PAYMENTS is receiving entries but does not fully match SALES. Among 25 explicitly recurring arrangements with positive recorded-paid amounts in SALES, eight have no single-reference PAYMENTS entry and three have a different linked amount. All 174 recurring-tab paid/balance fields still match SALES because the tab derives from it. These findings concern source bookkeeping completeness, not a failure of the preview's transformation checks. Do not infer unpaid instalments from missing PAYMENTS entries or use this preview to send reminders before the exceptions are resolved.
