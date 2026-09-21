# Nomobug CP2 — current status and batch checklist

This is the current progress entry point. Older plans/profiles are historical,
not proof that a pipeline is built. Latest reconciliation includes the successful
Prospects and complete eight-tab operational Bronze/Silver batch.

Latest verification on 21 September 2026: the confirmed warranty policy is now encoded and the selected experiment is `warranty_risk_residential_3x_30d_v3`. It covers eligible residential 3x packages and predicts a recorded Calendar warranty signal within 30 days after the third service. Earlier 60-day models are superseded. The repaired Git repository now follows the current remote main
history on branch `codex/cp2-v2`; the pre-repair working tree and damaged Git
metadata are preserved in a separate recovery folder.

The CP1-to-CP2 requirements comparison is recorded in
[`CP2_GOAL_COVERAGE_AUDIT.md`](CP2_GOAL_COVERAGE_AUDIT.md). It distinguishes
implemented evidence from planned work and superseded proposal options.

The residential 4x/6x/12x repeated-coverage dataset is now implemented with 364
mature service intervals across 146 packages. It retains multiple claims and
shows only exploratory model value; see
[`WARRANTY_COVERAGE_MODEL_EVALUATION.md`](WARRANTY_COVERAGE_MODEL_EVALUATION.md).

## What the levels mean

### Dashboard calculation correction — 15 September 2026

- Corrected the status-field mix-up: only PAYMENTS' legacy completion status
  is unused. PAYMENT LINK WON remains a recorded outcome.
- Recurrence now partitions by sale and normalized address-text hash, preserving
  unit punctuation. Missing addresses are isolated per event. Historical events
  are sequenced before the 2026 reporting filter; future appointments are excluded.
  Generic additional visits do not establish a return signal on their own.
  Exact extracted text can miss spelling/format variants or incomplete addresses;
  this remains candidate property evidence, not verified property identity.
- Warranty and additional-visit difficulty components are now disjoint. The
  unsupported equal-weight composite is null; package-refund context cannot
  establish which visit or team was responsible.
- Three corrected views published successfully. Local suite: 99 passed.
  After the owner increased the custom query quota, the combined live BigQuery
  reconciliation passed on 15 September 2026. Its dry-run estimate and actual
  cost guard were 6,031,566 bytes, below the retained 100 MiB per-query cap.
  The validation-only job timeout is 10 minutes because the regex-heavy view
  expansion exceeded the former 120-second execution timeout; this does not
  increase the byte cap.

Latest Calendar matching checkpoint (14 September 2026): HTML block boundaries
are parsed before phone/email/address extraction; multiple SALES phones are
compared separately. Generic payment-method labels no longer count as unique
invoices, strongest match tier takes precedence, and name-only matches are not
automatic. The user-identified Ummi 3/3, 4/3 and 5/3 all link to CUST482;
Zaty, KinNurture and later Maestro examples also pass regression tests.
The CC three-sale sequence is now resolved using a guarded Sales closed-date,
total-session and Calendar 1/N anchor rule. A second Calendar-sequence resolver
now assigns shared-phone warranty/complimentary events to the latest eligible
package anchor even when the Sales closed date is missing or the address is a
different property. Calendar dbt build PASS=13 (three views, ten tests) on
14 September 2026, including address-format and shared-phone/property examples.
The shared-phone/date resolver now weighs available name and address agreement
before the newest close date. This corrected three first-house visits previously
assigned to the second-house sale and two Shaun visits previously assigned to
Lau's sale. Other multi-property cases remain under private review; do not
equate a shared phone number with one sale or one service property.
Owner-confirmed House 1/House 2 unit details place Ikhmal's House 2 warranty
with CUST811. The 3x House & Car service stream is linked to Fawwaz's newer
six-session sale CUST2198 using its 1/6 anchor and closing date. Punita's July
2/3 stays on the active CUST2264 sale despite a different Calendar address.
Syed's July House 2 3/3 stays on CUST2159. The owner confirmed that this visit
physically serviced House 1 because pests were present there; the Calendar
description address is the service location even though the title tracks the
House 2 package sequence. Do not infer service property from sale or title alone.
Ambiguous 2026 service candidates fell from 160 to 0. Nurasikin's two-house
package events resolve from normalized customer-name/property markers and
Calendar address context. FAFA's `8/10` and warranty events now
follow its existing 7-session sale; the earlier `4/3` and `5/3` warranty events
remain linked to the 3-session sale. The later `9/10` event shown in Calendar
is not in this Bronze snapshot yet. The private ambiguous review list is empty
for the current 2026 service snapshot; five service candidates remain unmatched
after the address-format update (one more linked by the existing guarded rules).
Calendar changes require a fresh
controlled Bronze snapshot to be reflected in the views.

Workbook = Google Sheets file. Tab = one table-like worksheet. Column = field.
Profiled means inspected, not loaded. Bronze means preserved raw snapshot.
Initial Silver means some names/parsing/flags exist, not every business rule is
validated. Gold is the reporting layer; core fact views plus provisional
monthly, spatial, weather, recurrence, scheduling, refund, package-fit and
quality views are built. Cash-received, conversion and formal warranty
aggregates are not yet approved KPIs.

## All sixteen known tabs

| Workbook / tab | Scope | Latest API rows / columns | Bronze | Silver | Remaining |
|---|---|---|---|---|---|
| Prospects / 2026 | Primary | 32,580 / 24 | Verified | Initial + manual refresh | Complete rules, matching, production refresh |
| Prospects / B2B FOLLOW UP | Primary | 275 / 25 | Verified | Initial | Dates, visit/quotation/follow-up semantics |
| Prospects / FUTURE FOLLOW UP | Not selected | Not re-read | None in current pipeline | None | Excluded from first implementation |
| Prospects / Year End Promo 2025 | Not selected | Not re-read | None in current pipeline | None | Historical promotion, excluded |
| Prospects / B2B | Not selected | Not re-read | None in current pipeline | None | B2B FOLLOW UP selected instead |
| Prospects / RM399 PROMO | Not selected | Not re-read | None in current pipeline | None | Campaign-specific, excluded |
| Prospects / Experiment | Excluded | Not re-read | None | None | Do not ingest |
| Prospects / Experiment 13.01.26 | Excluded | Not re-read | None | None | Do not ingest |
| Session & Payment / SALES | Primary | 18,064 / 43 | Verified | Initial | Dates, categories, invoice/cadence/balance meaning |
| Session & Payment / PAYMENTS | Primary | 3,215 / 12 | Verified | Initial + sales links | Date/status meaning, invalid entries, duplicate receipt review |
| Session & Payment / PAYMENT LINK | Primary | 2,252 / 9 | Verified | Initial | Status/date semantics and phone/sale reconciliation |
| Session & Payment / WARRANTY CLAIM | Primary | 382 / 18 | Verified | Initial; one-row-per-claim Gold fact | Technician unpivot and Calendar linking |
| Session & Payment / REFUND | Primary | 54 / 11 | Verified | Initial (bank fields excluded); one-row-per-refund Gold fact | Date/status validation before a refund KPI |
| Session & Payment / Commercial Clients | Supporting/derived | 370 / 30 | Verified | Initial | Reconcile to SALES; do not count as new sales |
| Session & Payment / Recurring Payments | Supporting/derived | 166 / 33 | Verified | Initial | Determine payment-field types, unpivot, reconcile cadence |
| Session & Payment / LTV | Excluded by owner | Not re-read | None in current pipeline | None | Do not ingest |

Counts are API-returned rows, including templates and repeated entries, NOT
business-record totals. All available source dates were read, not only 2026 sales.
Nine in-scope tabs contain 205 returned columns. Allocated Sheet width is different.

Calendar profile checkpoint (13 September 2026): all six approved calendars were
read through the local end date with complete pagination. The active-only profile
found 10,690 events; the approved Bronze run includes cancelled events and stores
11,214 event rows with 11,214 calendar/event ID combinations. The first safe Silver
view is deployed without raw descriptions or locations; those remain restricted
to Bronze for controlled matching only.

## Column checklist

- config/full_sheet_column_checklist.csv: every one of the 205 positions, including
  blanks and duplicate headers; current tab stage, treatment, remaining check.
- config/operational_column_dictionary.csv: detailed draft names/types for all 80
  B2B/SALES/PAYMENTS fields. Raw values remain STRING; proposed types are not claims
  that parsing or business meaning is already validated.
- Readable raw aliases for the first 80 B2B/SALES/PAYMENTS fields are now in the
  dbt macro and views. The five new views keep positional raw fields and add only
  conservative labels; no unconfirmed dates or payment allocations are invented.
- config/data_dictionary_draft.csv is the older concept-level draft, not the
  authoritative 205-field coverage checklist. Unconfirmed entries remain tentative.

## What is deployed and verified

Thirteen Silver views are now deployed: prospects_2026, eight operational source
views, payment_sales_links, calendar_events and the restricted
calendar_event_matches view, plus `warranty_calendar_visits`. The latest operational dbt run completed 9 views and
13 data tests with PASS=22 total dbt steps; the Calendar batch completed 3 views
and 7 tests with PASS=10; the Gold build completed 9 views, one owner
disposition seed and 31 tests with PASS=41. Prospects remains a separate refresh selection. Local
tests now pass: 78, including complete 205-position checklist coverage and 80
readable raw-name coverage. Read-only compiled model and integrity checks also
passed before publication. Gold has 2,428 identified SALES rows, of which
2,427 currently qualify for a sale count after the CUST527 cancellation,
3,215 payment entries and 7,652 scheduled service-like Calendar entries;
2,407 sale totals parse, while two filled totals need review. These counts
are source records, not unique customers or completed treatments. Neon remains the manual fallback with its earlier
snapshot; no auto failover.

The Silver Prospects view now points to a 12 September extraction: it still
contains 32,580 rows, but 15,889 are prospect candidates (the earlier 15,696
candidate count came from a prior snapshot). The monthly first-reply view uses
the current pinned snapshot and does not join enquiries to sales.

## Audit checkpoint — 14 September 2026

- Fixed the `RM`-prefixed SALES total parser. Before the fix, all 2,407
  parseable `Total (RM)` values were null in Silver. The parser now accepts
  `RM490.00` and `RM 490.00`; all 22 operational dbt steps pass.
- The 382 WARRANTY CLAIM source rows yield 1,873 rows in the existing
  `warranty_calendar_visits` same-sale timeline, including 1,117 ordinary
  service joins. Joined rows must not be called claim counts or warranty visits.
- Owner clarified the PAYMENTS completion-status column is no longer updated;
  Gold ignores it. Of 3,215 payment entries, 3,197 amounts parse. Combined
  references remain one payment each and are not allocated per sale.
- The PAYMENTS displayed date omits its year, but the live Sheets API returns
  an underlying date serial. A versioned, exact-row-verified Bronze date sidecar
  is pinned to the existing PAYMENTS snapshot: all 3,215 row positions and
  displayed date/reference cells match. Gold dates 3,198 serial-valued rows
  directly (24 in 2024, 2,109 in 2025, 1,065 in 2026); two misspelled text
  dates remain undated/review, and 15 blank template rows remain undated.
  Three serial dates fall after the 14 September 2026 inspection date and are
  flagged, not silently treated as settled payments. No date year was inferred
  from sheet order; one 2025-12-31 row sits between 2025-01-01 rows.
- Owner confirmed CUST527 cancelled its service. A source-preserving disposition
  override flags this SALES row out of sale counts; its `PENDING` total stays raw
  and null numerically. CUST153's `ffi` total still needs owner review.
- Owner clarified that the early SALES records were kept without an exact entry
  timestamp; this is historical recording practice, not a missing-data error.
  Their Closed Date cells contain day/month. Rows 5-408 run from March to
  December and the first timestamped row, 409, is 29 December 2024. This
  supports a flagged 2024 year inference for the early block. Gold now has a
  `closed_date` for 2,423 of 2,428 identified SALES packages: 2,018 dated
  directly from entry-timestamp year, 400 from the early sequence, and five
  from agreeing adjacent timestamp years. The five undated packages retain
  their raw values and review flags. The year provenance is visible in
  `closed_date_year_source`; inferred years are not presented as source facts.
- Gold facts preserve the sale, payment and Calendar grains. No personal phone,
  email, address, Calendar description, or refund bank fields are projected.
- Separate Gold facts now preserve all 54 REFUND records and 382 formal WARRANTY
  CLAIM records at one row each. Exact SALES IDs link 53 refunds and 380 claims;
  the other IDs remain unmatched, not discarded. One refund amount is ambiguous
  (`490 or 390`), six REFUND Date cells contain amount-like text, and three
  claim dates lack a year. These are review flags. REFUND `COMPLETE` and the
  WARRANTY CLAIM refund indicator are source annotations, not cash proof.
  Neither Gold fact multiplies claims by Calendar entries. The earlier
  41-step Gold dbt build, including reconciliation tests, passed on 14
  September 2026; the current spatial/weather Gold build is recorded below.
- Four additional Gold views group recorded SALES package value, PAYMENTS entry
  amounts and 2026 first replies by month, plus overlapping quality-issue
  counts. Null-month rows remain visible. These are provisional descriptions
  of source records, not earned revenue, confirmed cash, sale conversion or
  completed treatments. The monthly reconciliation test checks fact totals.
- Historical baseline: 1,768 of 2,428 identified SALES rows contain a
  five-digit postcode-like pattern in their address; 2,045 of 2,776 dated
  2026 service-like Calendar events link to a sale with such a pattern. This
  pattern is not a validated postcode or coordinate. This historical shape
  check predates the Calendar-event geocoding layer below.
- A read-only 2026 Calendar location check covers all 2,776 service-like
  event rows without join expansion. The expanded address-label parser handles
  `Alamat`, `Address`, `Addresses`, `Addres`, `Full Address`, inline labels,
  markdown asterisks and missing colons after `Alamat`. A separate, narrow
  fallback recognises unlabelled numbered street/premise lines for location
  review; it is not used to create address-only SALES matches. All 2,776 now yield
  an event-address string, but this is format extraction, not address
  validation. Of these, 2,771 link to a SALES row, and 2,011 (72.4%) have a
  five-digit postcode-shaped token on the extracted event-address line. A
  linked SALES address has such a token on 2,040 event rows; 37 rows have it
  only in SALES, and seven rows with both tokens disagree. The earlier 2,045
  weather-readiness count used a different broad address-pattern check and
  should not be mixed with this event-address-line comparison. These
  discrepancies matter because
  the same customer can use a different property; never substitute the SALES
  address as the service location automatically. At this earlier checkpoint,
  no coordinates or weather had been loaded; the 15 September geocoding,
  weather and spatial results below supersede that readiness status.
  Reproduce the aggregate with `python scripts/inspect_weather_location_readiness.py`.
- Follow-up address-format check: the 765 events without a postcode-shaped
  token on the extracted address line still have address text; 706 of those
  lines contain other digits such as unit or street numbers. The Calendar
  `location` field supplies no additional text for these events. A 5-digit
  pattern appears elsewhere in 48 descriptions, but those numbers are not
  automatically accepted as postcodes because other fields can contain them.
  Across all dates in the pinned Calendar snapshot, 13 older unlabelled
  street-line descriptions were recovered; just one of 7,652 service-like
  entries remains without extractable address text, and that entry has an
  empty description. Missing postcodes alone do not block name/phone-based
  matching or necessarily prevent later address geocoding. Exact service-property
  recognition and coordinates still require validation; do not equate this
  format check with failed geocoding or inaccessible customers.
- Location validation gates and privacy/cost hold are recorded in
  `planning/LOCATION_VALIDATION.md`. The local multi-line prototype found 30
  address-like continuation lines with a five-digit token, raising candidate
  address-block coverage to 2,041/2,776 events; 735 lack a token in the
  cautious block. This does not validate postcodes or coordinates. No
  geocoding or weather enrichment had run at that checkpoint.
- Conservative address-string grouping originally found 887 normalized candidate strings
  across the 2,776 events, not 887 verified properties. Fifteen linked SALES
  IDs have multiple strings, including true-looking location changes and mere
  formatting/incomplete-address variants. No automatic customer/property
  deduplication or SALES splitting was performed.
- On 15 September, the privacy-safe geocoding cleaner identified 787 distinct
  sendable address candidates covering 2,471/2,776 2026 service-like Calendar
  events. Geoapify cached 782 results; current rules accept coordinate
  candidates for 1,857 events and leave 601 in manual review. Five provider
  requests remain unresolved. Sanitized accepted rows are in
  `quality.calendar_event_geocodes_2026_v2`; no raw address or contact fields
  are stored there.
- On 17 September, historical weather was rebuilt at its honest analytical
  resolution: 31 service-region 0.1-degree cells, 42,377 daily ECMWF IFS
  reanalysis rows from 18 December 2022 through 14 September 2026. All 31 cells
  loaded after resumable HTTP-429 retries. Event-level Gold retains local-grid
  features where a validated event location exists; the ML cohort uses an
  explicit service-region daily mean fallback otherwise. Neither is a
  property observation or proof of causation.
- The Calendar warranty rule is now explicit: post-package sequences such as
  `4/3` and `5/3`, including titles labelled complimentary, are warranty-claim
  candidates; explicit Warranty/Claim/Callback titles cover free follow-ups on
  6-session and 12-session/yearly packages. The current snapshot has 1,092
  post-package and 110 explicit warranty candidates. Fine-location coverage is
  215/1,202 warranty-claim candidates; among those fine-location events,
  event-day weather is available for 192, with 183 complete prior-14-day
  windows. The spatial Gold layer tests DBSCAN
  at 1/2/5 km and adds a scheduled-service denominator by area. The current
  53-step Gold build and 99 local tests pass.
- The updated complete-window weather comparison shows no obvious unadjusted
  separation: prior-seven-day rain averages 35.32 mm for 247 warranty-claim
  candidates and 35.54 mm for 1,206 normal scheduled-service entries. Humidity
  and soil-moisture means are likewise close. This is descriptive only and does
  not control for month, area, service type or repeated properties; do not
  market weather as a strong driver from this checkpoint.
- On 15 September, provisional Gold marts for recurrence windows, scheduling
  workload, refund-monthly review, package-fit evidence, treatment-difficulty
  proxy and PAYMENT LINK funnel records compiled successfully and seven views
  materialized as BigQuery views with `0 processed`. The local test suite still
  passes 99 tests. After the custom quota was increased, the combined live
  reconciliation passed within the 100 MiB query guard (6,031,566 bytes).
- The selected predictive experiment is now `warranty_risk_residential_3x_30d_v3`. It excludes all commercial clients and residential 1x packages, and uses a mature 30-day window after the residential 3x completion anchor.
- The selected L2 logistic model averages ROC AUC 0.519 and average precision 0.254 across three pre-2026 walk-forward folds. On the already-inspected 2026 complete-weather cohort it has ROC AUC 0.547 and average precision 0.293 (26.2% prevalence). This is weak discrimination, so the model remains an experimental review-ranking aid.

- The selected 56-feature contract includes prediction-time-safe operational and prior-weather variables while excluding event-day weather, team identity, salesperson/acquisition, payment behaviour and static environmental context.
- Static environmental features did not improve pre-2026 evidence: mean average precision changed from 0.2535 to 0.2496. The small 2026 diagnostic gain is insufficient for promotion; see `planning/ENVIRONMENTAL_MODEL_EVALUATION.md`.
- DBSCAN now operates on 108 distinct service properties containing 215
  recorded warranty signals, rather than directly on repeated event rows. With
  a minimum of three distinct properties, the 1 km view has 4 clusters/13
  properties, 2 km has 7/32, and 5 km has 4/95. These are sensitivity scenarios,
  not pest-spread radii.
- Finance exception review remains explicit: 13 PAYMENTS rows reference
  unmatched/combined IDs (the four `CUST 501`-style spacing variants are
  normalized by the Silver parser); three amounts are nonnumeric placeholders
  (`TESTING`/`Pest Control`), and two identical `CUST1575` rows remain because
  identical entries do not prove a duplicate receipt. No payment was deleted
  or allocated automatically.
- The source and model audit covers the critical financial, matching and
  warranty joins; it does not certify every one of the 205 source columns.
- Repository metadata was repaired from a fresh clone. The pre-repair working tree and damaged metadata remain preserved in the documented recovery folder.

## Remaining work in batches — no one-field-at-a-time handoff

1. **Full sheet coverage:** inspect all nine approved tabs, record all 205 columns,
   distinguish deployed vs draft, collect unknowns. DONE.
2. **Finish sheet contracts and safe raw loading:** PAYMENT LINK, WARRANTY, REFUND
   plus supporting derived tabs together; protect bank data; check headers/rows. DONE.
3. **Complete sheet Silver rules:** parse dates/categories with evidence, retain
   unknowns, unpivot warranty/recurring structures, validate joins and amounts.
4. **Calendar batch:** six approved calendars together; current metadata and event
   shape, bounded complete pagination, recurring/cancelled events, links to sales.
   Bronze, safe event Silver, restricted matching, and claim-to-Calendar visit
   timeline are DONE for the current snapshot. Current 2026 service-candidate
   counts are in the checkpoint above. Future shared-phone packages still
   require evidence-based disambiguation; cancelled/consultation/other events
   are not failed service matches. The claim-related timeline uses Calendar dates, while
   technician attribution and formal claim validation remain to be completed.
5. **Gold + enrichment:** first sale/payment/Calendar/refund/formal-claim facts,
   bounded date parsing and provisional recorded-activity/quality marts DONE.
   Location candidates, cached weather features and a sensitivity-tested
   spatial foundation are DONE with explicit partial-coverage flags. The
   dashboard-facing monthly service, package warranty, recurrence, scheduling,
   refund, descriptive package-fit and treatment-difficulty proxy views are now
   built and live-reconciled as provisional Gold marts. Next is Looker Studio
   wiring plus validation of
   business-approved finance, refund, conversion and proxy-score definitions.
   The objective-by-objective gap list is in
   `planning/CP2_GOAL_COVERAGE_AUDIT.md`.
6. **ML + spatial analysis:** 60-day target/label feasibility, pre-2026
   walk-forward model selection, prediction-safe feature controls and
   property-level DBSCAN sensitivity are DONE for the narrow three-session
   target. The model shows modest ranking value but unstable development folds
   and does not support production prediction. Future improvement requires an
   independent later test period plus confirmed completion/recurrence and
   treatment-quality evidence.
7. **Production hardening:** Cloud Run Jobs + Scheduler, authentication, retention,
   idempotency, locking, staged publication/rollback and audit logs. GitHub Actions
   for CI/deployment, not the selected production scheduler.
8. **Dashboard and release:** Looker Studio, access/privacy, user testing and docs.

Looker checkpoint (15 September 2026): five privacy-safe release views now cover
aggregate recurrence, geohash-area mapping, DBSCAN sensitivity clusters, monthly
weather associations and held-out ML evaluation. Exact event coordinates and
individual prediction rows are excluded. The focused Looker build completed 21
dbt steps successfully; `planning/LOOKER_STUDIO_BUILD_SPEC.md` records the page,
field, denominator and privacy contract. The Looker Studio report itself, viewer
access and rendered usability checks are still pending.
The signed-in Looker Studio account setup is open at its final email-preference
step. Country Malaysia, company Nomobug and the service terms are recorded; no
email subscription choices or final account-setup submission were made without
the owner's confirmation.

Calendar supplies accurate service dates, but scheduled events alone do not prove
service completion. Sales IDs identify packages/purchases, not unique people.
Combined payment amounts are counted once; per-sale allocations remain unknown.

## Grouped unresolved items (not a demand to answer now)

- Meaning/position of #VALUE! F vs AG, TRBS, blank-header fields and formula outputs.
- Date parsing/order and semantic meaning across tabs; Calendar authority preserved.
- PAYMENTS malformed/missing amount text and duplicate receipt evidence;
  the legacy completion-status column is intentionally ignored.
- Duplicate receipt evidence; annotation/phone ID exceptions; combined allocation.
- Recurring payment cells: amount/date/status; yearly cadence representation.
- Warranty claim versus service timestamps, technician sequence and refund status.

Continue safe work with explicit unknown flags. Ask one consolidated review only
when answers would change financial/operational interpretations or block a build.

## Schedule and tools

User target: September technical work; October dashboards; November polishing.
These are targets, not a claim that all remaining work fits the remaining hours.
Reassess against working increments and available one-hour sessions.
Selected stack: Python/pandas, BigQuery, dbt, scikit-learn + DBSCAN, Cloud Run Jobs
+ Scheduler, Docker, Looker Studio; GitHub Actions CI; Neon manual fallback.

No command is required for this checklist checkpoint. Read the status page first.
