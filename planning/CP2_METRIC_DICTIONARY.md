# CP2 metric dictionary — management meaning

This glossary explains what the data can answer before building charts. It uses the current source definitions as of 1 October 2026. The [dashboard build guide](CP2_DASHBOARD_BUILD_GUIDE.md) explains each management page; the [field reference](CP2_DASHBOARD_FIELD_REFERENCE.md) gives its exact Looker Studio source and field settings. The [dashboard handoff](CP2_DASHBOARD_HANDOFF.md) identifies the approved stable Gold views.

## Read every number with its unit and date

A **dimension** is something used to group or filter records: month, package, pest label, contract label or Calendar. A **metric** is a number calculated from those records: package count, recorded value, visit count or a share. The **grain** says what one row represents. Keeping grains separate prevents the same money or activity being counted several times.

| Record/unit | What one record means | What it does not establish |
|---|---|---|
| Enquiry candidate | A candidate enquiry row in the 2026 prospect tab | A unique person, a sale, or a new customer |
| Sales package | An identified SALES row, normally one sale/package ID | A unique customer or property |
| Payment entry | One PAYMENTS sheet row | Verified settlement or money allocated separately to every referenced sale |
| Payment-link record | One PAYMENT LINK source row | A unique lead or a reconciled conversion funnel |
| Calendar service entry | A confirmed service-like scheduled/recorded Calendar entry | Proof the treatment was completed |
| Calendar warranty signal | An entry classified using warranty/callback wording or an over-package sequence such as `4/3` | A separate formal claim row, verified reinfestation or proof of treatment failure |
| Formal warranty claim | One WARRANTY CLAIM sheet row | A Calendar visit or completed warranty treatment |
| Refund record | One REFUND sheet row | Proof money was transferred back |
| Model example | One eligible matched paid-service anchor and its 30-day outcome window | A unique customer or contractual warranty decision |

For example, a person can buy two packages, make one combined payment, have six Calendar entries and file one formal claim. Those are two package records, one payment entry, six visit entries and one claim. Adding or dividing these counts without a declared relationship produces a misleading result.

The source column called **Customer ID** is a sale/package ID in this project. Use the label **Packages sold** for package counts. A company-wide unique-customer count requires a validated person/business identity that the current aggregate report does not provide.

Dates have different meanings. Sales use the recorded close date; payments use the payment-entry date; enquiries use the first staff reply date; visits use the Calendar date in Malaysia time. These can fall in different months for the same package. Date controls must use the date relevant to each measure.

## Sales value and packages sold

Source: `gold.sales_monthly_recorded`. One row is one source snapshot and close month. Null close months preserve unresolved dates. Use `closed_month` as the chart date dimension.

| Field | Management label and meaning | How to aggregate |
|---|---|---|
| `countable_package_rows` | **Packages sold:** included package rows with a resolved close date that is not in the future | SUM |
| `recorded_package_face_value_rm` | **Recorded package value (RM):** parseable package totals for those countable packages | SUM; currency RM |
| `package_rows` | **Sales source package rows:** all identified package rows, including exceptions | SUM; use for source reconciliation |
| `unparsed_or_blank_total_rows` | Included rows whose total is blank or cannot be parsed | SUM; show in exceptions |
| `excluded_disposition_rows` | Rows excluded by an owner-confirmed disposition override | SUM; excluded from packages sold/value |
| `undated_rows` | Rows without a resolved close date | SUM; preserve the null-month group |
| `future_dated_rows` | Rows with a close date after today's Malaysia date | SUM; excluded from current sales/value |
| `inferred_year_rows` | Close dates whose year came from chronological entry evidence rather than an exact recorded entry timestamp | SUM; show as date-quality context |
| `closed_month` | Month of the interpreted close date | Date dimension; null means unresolved |
| `snapshot_table` | Immutable source snapshot supporting these rows | Metadata; never SUM or use as a customer dimension |

Package value is what the package record says it was sold for. It is not earned revenue, profit or settled cash. Missing amounts stay missing; a SUM can still return a number when some packages have no usable total. Display the missing-total count beside financial summaries.

Do not call `SUM(recorded_package_face_value_rm) / SUM(countable_package_rows)` the average price of packages with known prices: the denominator includes countable packages with missing totals. If used, label it **Recorded value per counted package**, disclose missing totals, and retain it as a descriptive indicator. A priced-package average needs an additional validated count of packages with usable totals.

The source often omits the close-date year in earlier records. The model records whether the year came from an entry timestamp, the early chronological sequence, adjacent entry years, or remained unresolved. Show inferred dates as a quality limitation; do not silently replace unresolved dates with January or the current year.

## Payments recorded

Source: `gold.payments_monthly_recorded`. One row is one source snapshot and payment month. Use `payment_month` as the date dimension.

| Field | Management label and meaning | How to aggregate |
|---|---|---|
| `recorded_payment_entry_amount_rm` | **Payments recorded (RM):** parseable amounts on dated, nonfuture payment entries, each counted once | SUM; currency RM |
| `dated_nonfuture_rows` | Payment entries with a resolved date no later than today's Malaysia date | SUM |
| `payment_rows` | All PAYMENTS source rows retained for reconciliation | SUM; does not imply all are genuine receipts |
| `unparsed_or_blank_amount_rows` | Rows with no usable amount | SUM |
| `text_date_review_rows` | Date cells that are text rather than a verified spreadsheet date serial | SUM |
| `undated_rows` | Rows without a resolved payment date | SUM; keep null-month exceptions |
| `future_dated_rows` | Rows dated after today's Malaysia date | SUM; excluded from current recorded amount |
| `combined_reference_rows` | Payment entries referring to several sale IDs | SUM; a combined amount remains one amount |
| `reference_review_rows` | Missing, unrecognized or repeated sale-reference evidence | SUM |
| `payment_month` | Month of the underlying verified spreadsheet date | Date dimension |
| `snapshot_table` | Source snapshot supporting the entries | Metadata |

The displayed spreadsheet date can omit its year. The reporting pipeline reads the same cells' underlying serial dates to preserve the year. A dated payment entry still does not prove bank settlement. The owner confirmed the old PAYMENTS completion-status column is unused; the dashboard does not interpret it as paid/unpaid.

Never sum a combined amount once for each sale to which it links. Do not subtract recorded payment amounts from package value as an outstanding-balance KPI: the reporting sources do not yet allocate combined receipts or reconcile settlement. Keep sales and payment trends separate, with their own date labels.

## Enquiries and recorded conversation outcomes

Source: `gold.prospect_reply_monthly_recorded`. One row is one prospect snapshot and first staff reply month. The owner confirmed that the source tab represents 2026 and that ENGAGE means the first staff reply. A candidate row has a phone or first-reply entry; automatic follow-up placeholders are excluded.

| Field | Management label and meaning | How to aggregate |
|---|---|---|
| `prospect_candidate_rows` | **Enquiry candidate records:** candidate rows in the prospect tab | SUM; not unique leads |
| `recorded_open_rows` | Candidate rows annotated OPEN | SUM |
| `recorded_closed_rows` | Candidate rows annotated CLOSED, including the recognized spelling variant | SUM; CLOSED does not mean WON |
| `exact_won_remark_rows` | Rows with an exact WON remark | SUM; missing WON does not mean lost |
| `undated_first_reply_rows` | Candidate rows without a usable first staff reply date | SUM; keep null-month exceptions |
| `future_first_reply_rows` | Candidate rows whose reply date is later than today | SUM; review before interpreting as historical activity |
| `acquisition_review_rows` | Rows with an acquisition label that needs classification review | SUM |
| `first_reply_month` | Month of first staff reply | Date dimension; not enquiry arrival or sale month |
| `snapshot_id` | Prospect snapshot identifier | Metadata |
| `snapshot_extracted_at` | When that snapshot was extracted | MAX for latest timestamp; never SUM |

The current monthly aggregate does not expose acquisition channel, staff PIC, customer type or pest dimensions. It cannot supply those filters or breakdowns. A first-reply date alone does not provide response time because a validated enquiry-arrival timestamp is also required. Do not present CLOSED/total as sale conversion, or link prospect rows to sales through a guessed denominator.

## Payment-link records

Source: `gold.dashboard_payment_link_monthly`. One row is one interpreted payment-link month. Use `payment_link_month` for its date dimension.

| Field | Meaning | How to aggregate |
|---|---|---|
| `payment_link_source_rows` | PAYMENT LINK source rows, without a reconciled unique-lead denominator | SUM; label **Payment-link source records** |
| `recorded_won_rows` | Rows with the exact recorded WON outcome | SUM; label **Recorded WON outcomes** |
| `missing_status_rows` | Rows without a recorded outcome/status | SUM |
| `date_review_rows` | Rows without a parsed full-year date | SUM; preserve null month |
| `outcome_text_rows` | Rows containing any outcome text | SUM |
| `payment_link_month` | Month of a parsed source link date | Date dimension |
| `denominator_evidence` | Text explaining the source-record denominator | Metadata/caveat |

WON here is meaningful recorded evidence. This is a different column from the unused PAYMENTS completion-status field. However, raw source rows can include unqualified/template rows, and links are not reconciled to the prospect and sales populations. Show counts; do not call WON/source rows the company's conversion rate.

## Pest, package and contract context

Source: `gold.dashboard_package_fit_matrix`. One row is one `pest_type` × `package_type` × `contract_type` combination. These are recorded source labels, not predicted needs. A bundled pest label can cover more than one pest. Keep the bundle intact when counting packages or money to avoid duplication.

| Field | Meaning | How to aggregate |
|---|---|---|
| `pest_type` | Recorded pest/bundle label | Dimension |
| `package_type` | Recorded package label | Dimension |
| `contract_type` | Recorded contract label | Dimension |
| `package_rows` | Included package rows in that combination | SUM |
| `recorded_package_face_value_rm` | Sum of usable recorded package totals | SUM; RM |
| `packages_with_payment_evidence` | Packages having at least one linked PAYMENTS entry | SUM |
| `linked_payment_entry_rows` | Linked payment-entry references across these packages | SUM as linked evidence, never total distinct company receipts |
| `scheduled_event_rows` | Linked 2026 scheduled/recorded Calendar entries | SUM |
| `warranty_claim_event_rows` | Linked Calendar warranty-signal entries | SUM |
| `generic_complimentary_event_rows` | Linked complimentary entries without a warranty signal | SUM |
| `payment_evidence_rate` | Packages with linked payment evidence / package rows | Recalculate from SUM of the two count fields |
| `warranty_event_share` | Warranty-signal entries / scheduled entries | Recalculate from SUM of the two event fields |
| `denominator_evidence` | Descriptive evidence warning | Metadata/caveat |

**This view has no date field.** Its current SQL includes package close dates across calendar 2026 and Calendar activity across calendar 2026, including recorded future dates. Label it **Recorded 2026 package context**. It cannot respond honestly to a selected-month filter or supply current-period sales totals. Use the monthly sources for those totals.

Payment evidence means a linked sheet entry exists; it does not mean that the package is fully paid. Combined payment entries can link to several packages, so linked evidence counts do not equal distinct receipts. This matrix can support a discussion of package mix and recorded follow-up burden. It does not identify rejected offers, prove a package causes better results, or recommend a predictive upsell.

## Customer and package fields in the internal foundation

The following fields explain source meaning. They are not an instruction to connect private fact views to the management report; use approved aggregate sources. Some are unavailable as dimensions in the current aggregate release.

| Internal field | Meaning and limit |
|---|---|
| `sales_record_id` | Sale/package identifier; never a unique person ID |
| `package_sessions_recorded` | Number of sessions recorded for that sale row; linked upsells may require episode reconciliation |
| `premise_type` | RESIDENTIAL, COMMERCIAL, VEHICLE or UNKNOWN based on the recorded premise label |
| `package_type_raw`, `pest_type_raw`, `contract_type_raw` | Source labels; blanks/variants require review before a normalized category comparison |
| `recorded_returning_client` | TRUE when relationship text contains OLD or RETURNING; FALSE does not establish a new client |
| `acquisition_relationship_raw` | Original sale relationship/source label; not a deduplicated acquisition history |
| `sales_pic` | Recorded sales person-in-charge label; not attribution of every follow-up or service |
| `billing_arrangement`, `trbs_status` | Recorded source labels; do not invent an interpretation or a settled-payment status |
| `days_first_contact_to_close` | Interpreted interval between recorded first contact and close date; can use inferred year evidence, and is not first-response time |
| `deposit_recorded_rm`, `balance_recorded_rm` | Parseable values in the SALES row; not reconciled PAYMENTS transactions or verified settlement |
| `sale_disposition`, `include_in_sale_count` | Owner-confirmed exclusion rule and whether the package is included |
| `closed_date_year_source` | Entry-timestamp, chronological inference, or unresolved evidence for the year |
| `closed_date_missing`, `closed_date_needs_review`, `sale_total_needs_review` | Quality flags; null values stay visible rather than silently becoming zero |
| `source_sheet_row`, `sales_row_id`, `snapshot_table` | Traceability metadata; not business KPIs |

The prospect foundation separately records acquisition groups such as business ads, regular ads, unspecified ads, website, social channels, Google, call, referral, returning-customer label, missing, unknown and unresolved. Campaign audience is separate from recorded residential/business customer type. These require a privacy-approved aggregate before dashboard charts can use them.

## Warranty policy and recorded signals

The owner's policy applies regardless of pest:

| Package/premise | Warranty policy |
|---|---|
| Commercial, any package | No warranty |
| Residential 1x | No warranty |
| Residential 3x | Claim within 30 days after the third/final paid service |
| Residential 4x, 6x or 12x | Unlimited claims during the service period, plus 30 days after the final paid service |
| Unknown/undefined premise or package | Review the policy evidence |

An initial 1x followed by Upsell 2x can form a confirmed 3-service episode even when individual Calendar descriptions still say 1x. Use reconciled episode evidence, not one uncorrected description, to interpret it. `4/3` means a visit beyond the three paid package sessions and is classified as a warranty signal under the agreed rules. Generic complimentary visits without that evidence remain separate.

Policy eligibility, Calendar warranty-signal classification, formal claim counts and the model's callback outcome answer different questions. The internal `warranty_policy_eligible`, `warranty_policy_category` and `warranty_policy_rule` describe the package policy. They do not prove a claim was timely, approved or completed.

`dashboard_warranty_package_metrics` has one row per matched package with 2026 Calendar activity. It contains `scheduled_service_event_rows`, `normal_package_service_event_rows`, `warranty_claim_event_rows`, `generic_complimentary_event_rows`, `heatmap_eligible_event_rows`, `heatmap_eligible_warranty_claim_rows`, `warranty_claims_with_complete_prior_14d_weather`, `has_warranty_claim_signal`, `warranty_claim_event_share` and `heatmap_warranty_claim_share`. Its `closed_date` filters a **package-purchase cohort**, while `first_calendar_service_date` and `last_calendar_service_date` are timeline endpoints. These dates do not allow the stored counts to be filtered by event month. Keep this package-level source internal until an approved aggregate is provided.

## Refund and formal-claim records

Source: `gold.dashboard_refund_monthly`. One row is one interpreted refund month. Use `refund_month` as the date dimension, including the null-month exceptions group.

| Field | Meaning | How to aggregate |
|---|---|---|
| `refund_source_rows` | REFUND sheet rows | SUM |
| `linked_refund_rows` | Rows linked through an exact sale ID | SUM |
| `unmatched_refund_rows` | Rows without an exact sale match | SUM |
| `recorded_complete_rows` | Rows annotated COMPLETE | SUM; label **Refund records marked complete** |
| `status_review_rows` | Other or missing statuses | SUM |
| `amount_review_rows` | Rows without a usable amount | SUM |
| `date_review_rows` | Rows without a parsed full-year date | SUM |
| `recorded_refund_amount_rm` | Sum of usable amounts recorded in refund rows | SUM; RM; not cash returned |
| `refund_month` | Month of a resolvable refund date | Date dimension |
| `denominator_evidence` | Source-record and settlement warning | Metadata/caveat |

A REFUND amount can be usable while its date remains unresolved. A month-filtered chart can therefore omit an amount that still appears in the overall exception total. Day/month-only dates and amount-like text in a date cell are flagged rather than assigned a guessed year.

The internal `refund_record_facts` retains one refund record ID, source row/snapshot, exact-sale link status, raw date/amount evidence, parsed amount, amount-review flag and recorded status. It omits bank/contact fields. The internal `warranty_claim_record_facts` similarly retains one formal claim ID, exact-sale link status, parsed claim date/date-review flag and `source_refund_indicator`. A YES, NO or date annotation in that indicator does not prove a cash refund. Do not sum Calendar visits expanded around a claim as formal claims.

## Core service, location, weather and model meanings

These terms are developed in the page guide and field reference:

| Measure family | Meaning for management |
|---|---|
| Scheduled visit counts | Recorded Calendar workload; appointments can be future scheduled entries, and counts are not completed jobs |
| Warranty-signal share | Recorded warranty-signal entries divided by scheduled entries for the same population |
| Match coverage | Share of service entries matched to a sale/package; unmatched entries remain visible |
| Recorded return intervals | Time between source-backed warranty signals and preceding Calendar activity within the reconciled package/property context; not verified biological recurrence |
| Area signal share | Warranty signals relative to scheduled-entry volume in an aggregate geographic area; compare volumes and coverage beside shares |
| DBSCAN clusters | Descriptive groupings under 1, 2 and 5 km distance settings; settings are sensitivity scenarios, not pest travel distances or changes to frozen-model accuracy |
| Weather comparisons | Weather reanalysis associated with service locations/windows; complete-window coverage must accompany averages, and differences do not establish causation |
| Model probability | A frozen experimental score for a recorded corrective Calendar callback in days 1–30 after an eligible matched paid service |
| Held-out model results | Historical services excluded from model fitting/selection evaluation as documented; current v5 test has 100 services and five positive windows |
| Prospective collection coverage | Timely logged predictions and missed windows before future outcomes; it does not yet measure future prediction performance |

The model target is binary: callback recorded = 1; no such recorded callback in a fully observed 30-day window = 0. The output is a numerical probability/ranking. Contractual warranty eligibility is separate. The report exposes aggregate evaluation, not individual experimental risk scores. Read the [current model evidence](CP2_CORRECTED_MODEL_CANDIDATES_V5.md) before interpreting AUC, average precision or top-20 capture.

## Freshness, quality and aggregation rules

`dashboard_source_freshness` is one row per source. It exposes `source_name`, `snapshot_table`, `extracted_at_utc`, `release_run_id`, `hours_since_extraction` and `freshness_evidence`. Extraction time means when the immutable source snapshot was captured. It is not when an appointment happened, a payment settled, or a prediction was made. For the slowest source show MAX hours; for each source show its actual timestamp. A failed release retains the previous approved views, so a healthy-looking old total still needs visible freshness.

`dashboard_data_quality` has one row per source and issue code: `source_name`, `issue_code`, `affected_rows`, `source_rows`, `affected_share`, `reviewed_date` and `denominator_evidence`. The share is affected rows divided by that issue's source denominator. Issue populations overlap. Never add affected rows across issue codes to claim a total number of bad records, or sum repeated source denominators across those codes. `reviewed_date` is query/review context, not source extraction freshness.

Use these rules on every page:

- Sum count/value fields over compatible, nonoverlapping groups. Do not SUM IDs, timestamps, booleans, explanatory text or precomputed percentages.
- Recalculate a percentage from its summed numerator and denominator: `SUM(numerator) / SUM(denominator)`. Do not average subgroup percentages. Protect against a zero denominator.
- Null means unavailable/unresolved. Show it as Unknown/Needs review where appropriate; do not interpret it as zero or silently remove exceptions.
- A date filter applies only when the source carries the relevant date. Monthly aggregates cannot support daily response measures or equal-elapsed-day partial-month comparisons.
- State the period and denominator beside a share. A high percentage from a very small population needs its count and coverage.
- Use stable approved `gold` views. Source snapshot/candidate names are audit metadata, not extra report populations to add together.
- Keep names, contact details, addresses, bank details, raw Calendar descriptions, exact property coordinates and individual model scores outside this aggregate management report.

## Measures requiring more evidence

The current report can support package mix, recorded financial activity, scheduled workload, recorded warranty patterns, data-quality follow-up and cautious model evaluation. Do not invent the following KPIs from the current fields:

| Requested KPI | Missing evidence |
|---|---|
| Unique customers, active customers, new versus returning customers | Validated identity across purchases, contacts, businesses and properties; an absent returning marker is not a new-customer label |
| Customer retention/churn, customer lifetime value | Validated identities, observation periods and comparable purchase/service definitions |
| Acquisition channel conversion or marketing ROI | Approved channel aggregates, linked funnel populations, spend, attribution and reconciled outcomes |
| Revenue, profit, net cash, settled collections or outstanding balance | Recognition/settlement evidence, costs, refund transfers and allocation of combined payments |
| Completed jobs, technician productivity or capacity utilization | Validated actual completion status, staff assignment, actual duration and available staff hours |
| Warranty approval/completion rate or genuine treatment failure | Timely entitlement checks, approved/denied claim outcomes, completion evidence and verified pest outcomes |
| Predictive package/upsell recommendations | Offer history including rejected offers, validated outcome labels and a separate evaluated model |

Use the page guide to turn supported measures into decisions: review package demand, arrange scheduled workload, investigate documented warranty patterns and resolve source exceptions. Keep each action grounded in the displayed evidence.
