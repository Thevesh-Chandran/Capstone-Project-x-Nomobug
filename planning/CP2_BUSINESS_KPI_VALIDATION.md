# CP2 business KPI validation — 28 September 2026

**Assessment: ready within the checked *recorded-activity* scope, with freshness and business caveats.** A read-only acceptance run independently recomputed selected deployed reporting facts and monthly aggregates from their exact pinned, immutable Bronze snapshots. All **12 checks passed** across **20 BigQuery queries** (9.01 MB processed; each query capped at 100 MiB). It also compared the pinned Sheet inputs to a fresh private Sheets extraction taken on **27 September 2026**. Fresh changes exist and are **not** represented by the deployed Gold totals below.

## What the checks establish

The validator [script](../scripts/validate_business_kpis.py) reads the Bronze source rows, converts dates/amounts in Python, and compares both *membership and values* to deployed Silver/Gold records. It catches dropped or expanded joins even when aggregate totals happen to match. It then independently groups Bronze records into monthly figures and compares sales, payments, Calendar services, refunds, and prospects to the existing reporting views. Source B2B status annotations are checked at row grain, without inventing a conversion denominator. Owner-confirmed cancelled sales and Calendar warranty reviews are applied from their approved seeds.

| Checked source and reporting meaning | Evidence from pinned snapshots | Result |
|---|---:|---|
| SALES identified package facts and monthly face value | 2,428 identified package rows; 2,422 countable dated/nonfuture rows; RM 1,333,009.16 *face value* | Row and monthly checks pass |
| PAYMENTS record facts and monthly entry amounts | 3,215 rows; 3,195 dated/nonfuture; RM 990,866.39 *recorded entry amount*; 7 combined-reference rows counted once | Row and monthly checks pass |
| Calendar confirmed service-like entries and 2026 monthly counts | 7,647 service-like entries all dates; 2,776 dated 2026, including 463 Calendar warranty/callback signals | Row and monthly checks pass |
| REFUND rows and monthly source counts | 54 rows; one unparseable amount; RM 23,773.80 parseable recorded amounts | Row and monthly checks pass |
| Formal WARRANTY CLAIM sheet | 382 rows; three claim dates unresolved | Row-grain check passes |
| 2026 prospect candidates and monthly annotations | 15,889 candidate enquiry rows; 245 exact `WON` remarks | Row and monthly checks pass |
| B2B FOLLOW UP source annotations | 275 source rows; 261 phone-present rows | Row-grain check passes |

The 12 separate pass/fail results and queries are in the private run summary at `outputs/cp2-v2/kpi_validation_20260928_fresh/summary.json`, with private source evidence beside it. `outputs/` is ignored by Git and must remain private. The public report uses counts only. Representative source rows were checked by opaque example IDs in that summary: commercial and residential 1x without warranty, residential 3x and 12x policy categories, an owner-cancelled sale, a combined payment, an unknown payment amount, a Calendar callback, an unknown refund amount, an undated formal claim, and an exact prospect `WON` remark. These are **record-level examples**, not proof of every real-world sale, treatment, or transfer.

## Freshness check against 27 September Sheets

The warehouse's currently pinned SALES, PAYMENTS, REFUND, formal-claim, and B2B snapshots were extracted **13 September**; its 2026 prospect snapshot was extracted **12 September**. The pinned Calendar snapshot is also from **13 September**. The separate private live Sheets read on 27 September found the following changes in the selected KPI input columns and source-row membership:

| Sheet | Existing row positions whose selected inputs changed | Added rows (nonblank in selected inputs) | Interpretation |
|---|---:|---:|---|
| SALES | 37 | 0 | Current Gold sales summaries exclude subsequent edits |
| PAYMENTS | 15 | 22 (17) | Current Gold payment summaries exclude subsequent entries/edits |
| WARRANTY CLAIM | 0 | 5 (5) | Current formal-claim count excludes new rows |
| 2026 prospects | 358 | 0 | Current prospect summaries may have changed |
| B2B FOLLOW UP | 266 | 66 (33) | Large positional drift; row insertions/reordering may contribute |
| REFUND | 0 | 0 | No selected-input drift in this comparison |

These are **position comparisons**, not established counts of changed customers or proven deletions. They do not repoint Gold. Any released KPI labelled “current” must first run the governed source refresh/rebuild and revalidate against its new pinned snapshots. Model scoring and KPI publication have different source and release requirements.

## Interpretation limits and acceptance

1. **No financial settlement claim:** SALES totals are package face value, not earned revenue. PAYMENTS are recorded sheet entries, not bank-confirmed receipts. `COMPLETE` in REFUND is a source annotation, not transfer proof. Combined payment references are counted once, with no invented allocation to individual sales.
2. **No treatment-completion claim:** Calendar entries are scheduled/recorded service-like events. The 2026 monthly view includes 2026 dates under its current definition; neither Calendar nor SALES `Done Session` is independent completion evidence. Calendar callback signals and formal Sheet claim rows are different grains and must not be added as one claim total.
3. **Warranty policy boundaries:** Native SALES package flags are consistent with commercial no-warranty, residential 1x no-warranty, 3x post-third-service 30 days, and 4x/6x/12x active-service plus 30-day policy. **This validation does not prove each individual claim falls within its date window or resolve linked 1x + Upsell 2x entitlements.** The policy/episode model has separate checks; this KPI review should not be used as an entitlement decision.
4. **No conversion-rate claim:** Prospect `WON`/`CLOSED` and B2B statuses are recorded annotations. Prospect rows are enquiries, not unique customers, and no cross-source converted-customer denominator was reconciled. Likewise, the 405 inferred SALES close years are estimates disclosed by Gold, not source-recorded dates.

The 12 checks validate the deployed views against their **pinned source versions**. They do not establish present-day freshness or audited business outcomes. The next KPI release step is a separately reviewed fresh-source Bronze/Silver/Gold build, independent reconciliation against the new source pins, and owner confirmation for cash, completion, and conversion meanings if those stronger KPIs are wanted.

Run again, without changing sources:

```powershell
.venv\Scripts\python.exe scripts/validate_business_kpis.py --output-dir outputs/kpi_validation/run_20260928_example
```

Add `--fresh-source-json outputs/<private-live-run>/sheets_private.json` to compare fresh Sheet inputs while leaving Gold untouched. The CLI fails if any row or aggregate comparison fails and refuses to overwrite a prior run. The reusable `validate(output_dir, fresh_source_path=None)` API returns the report paths for a pipeline stage.
