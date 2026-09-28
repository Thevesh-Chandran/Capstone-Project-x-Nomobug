# Gold recorded-activity foundation

Build with `python scripts/build_gold_foundation.py` from the repository root
using the project virtual environment. The five fact views retain these grains:

- `sales_package_facts`: one identified SALES package row (Customer ID is a
  sale/package ID, not a unique person). `sale_total_rm` comes from `Total (RM)`;
  blank and malformed values remain null with review flags. Owner-confirmed
  cancellations are stored in a separate override seed; CUST527 is excluded
  from the sale-count flag while its source row remains available. The source
  close date has no year in many early rows because exact entry timestamps were
  not recorded then. `closed_date` uses the entry year when recorded, or an
  explicitly labelled year inferred from the chronological SALES sequence.
  Missing and malformed dates remain null and flagged; `closed_date_raw` is
  retained for review.
- `payment_record_facts`: one PAYMENTS row. Amounts are not allocated across
  combined references. The old completion-status column is ignored as directed
  by the owner; malformed/missing amounts remain flagged. The displayed source
  date omits its year, so `payment_date` comes from a separately verified,
  immutable Bronze snapshot of the same Google Sheets cells with
  `UNFORMATTED_VALUE`/`SERIAL_NUMBER`. The raw display remains available.
  Unparseable text and dates later than today's Kuala Lumpur date are flagged;
  blank template rows stay undated. A dated row alone is not proof of settlement.
- `calendar_service_event_facts`: one confirmed service-like Calendar entry.
  A confirmed entry is scheduled/recorded, not completion proof. Unmatched
  events remain visible through `match_status` and a null sale ID.
- `refund_record_facts`: one REFUND sheet entry. An exact SALES ID is linked
  when present; an unmatched ID remains visible. One ambiguous amount stays
  null, and amount-like text in six source Date cells is flagged rather than
  converted to a date. `recorded_complete` describes a sheet annotation, not
  proof that money was transferred. No bank or contact fields are projected.
- `warranty_claim_record_facts`: one formal WARRANTY CLAIM sheet row, with
  exact SALES ID linkage when available. Three day/month-only claim dates
  remain undated for review. The source refund indicator is an annotation,
  not evidence of a cash refund. Calendar visits are not multiplied into
  this claim grain, and a claim row is not a completed treatment count.

These are reporting-safe fact views, not final management KPIs. Do not sum
`warranty_calendar_visits` rows as claims or warranty treatments: it is a
same-sale timeline with a many-to-many claim/event expansion. No contact,
address, raw Calendar description or refund bank fields are exposed here.

Location and weather additions keep Calendar-event grain:

- `calendar_service_event_facts` exposes sanitized coordinate candidates and
  ECMWF IFS event-day/prior 3/7/14-day features when available. Weather is
  approximately 9 km reanalysis and supports association language only.
- `spatial_repeat_signal_events` contains only Calendar warranty-claim proxies:
  explicit warranty/claim/callback entries and over-package sequences such as
  `4/3` or `5/3` (including titles that say complimentary), with
  street-or-better coordinates. DBSCAN at 1, 2 and 5 km is sensitivity
  analysis, not a pest spread radius.
- `spatial_service_area_metrics` compares repeat-signal entries with scheduled
  service-entry volume by area. Cells with fewer than five entries are flagged;
  the denominator is not proof of completed treatments.
- `dashboard_service_monthly` provides the monthly KPI layer: scheduled service
  entries, warranty-claim signals, generic complimentary entries, matching
  coverage and heatmap/weather coverage. Its rates are event shares, not unique
  customer or completed-treatment rates.
- `dashboard_warranty_package_metrics` provides one row per matched SALES
  package with Calendar activity and warranty-claim signal counts. Customer IDs
  remain package IDs, so this is a package-level view rather than a person-level
  repeat-customer metric.
- `dashboard_recurrence_windows` compares Calendar intervals within a SALES
  package and exact normalized address-text hash, retaining unit punctuation.
  Missing addresses remain isolated. Historical events are included before
  filtering the report to 2026; future appointments are excluded. Exact text
  matching may miss address variants and is not verified property identity.
  Warranty signals qualify for interval buckets; generic extra visits need
  further evidence. It uses the
  proposal's 0–7, 8–14, 15–30, 31–60 and 61+ day buckets.
- `dashboard_scheduling_capacity` groups scheduled/recorded workload by local
  service date and Calendar. It is not completed-treatment hours or technician
  capacity until those fields are validated.
- `dashboard_refund_monthly` preserves unresolved date/amount and status counts
  and is not a cash-settlement KPI.
- `dashboard_package_fit_matrix` is descriptive package/pest/contract evidence
  with payment-entry evidence. It is not an upsell prediction and does not
  allocate combined payment amounts.
- `dashboard_payment_link_monthly` groups PAYMENT LINK source records and keeps
  recorded WON/missing-status/date-review counts. It is not a conversion rate
  until links and denominators are reconciled. The unused status column belongs
  to PAYMENTS; PAYMENT LINK WON remains a recorded outcome.
- `dashboard_treatment_difficulty` exposes separate warranty, non-warranty
  additional-visit and linked-refund context shares. Refund context is attached
  to packages, without proof of visit/team responsibility. Its composite score
  is null until weighting is validated; warranty is not counted twice.

Four additional views support provisional monthly reporting and quality review:

- `sales_monthly_recorded` groups identified package rows by `closed_month`.
  `recorded_package_face_value_rm` sums parseable package totals for included,
  dated, nonfuture sales. It is not earned revenue or cash. A null month keeps
  undated packages in the row count; cancellation and date/total issues are
  counted separately.
- `payments_monthly_recorded` groups payment entries by `payment_month`.
  `recorded_payment_entry_amount_rm` sums parseable, dated, nonfuture entries
  once each, including combined references only once. It is not verified cash
  received; duplicate receipts and settlement require further evidence.
- `prospect_reply_monthly_recorded` groups 2026 candidate enquiry rows by
  staff first-reply month. Its closed and exact-WON remark counts reflect
  annotations in that tab only; they are not conversion or unique-customer
  counts. Auto-filled follow-up dates are not used.
- `recorded_activity_quality` exposes issue counts with a denominator per
  source. Issues can overlap, so never sum its `affected_rows` across codes.

The monthly summaries deliberately keep null-month rows and separate review
counts. `gold_recorded_activity_reconciliation` checks their rows and amounts
against the fact views; `gold_refund_warranty_reconciliation` checks the two
source-record grains and exception handling. These views are not final finance,
warranty, refund or conversion KPIs until their business rules and
duplicate/settlement evidence are validated.
