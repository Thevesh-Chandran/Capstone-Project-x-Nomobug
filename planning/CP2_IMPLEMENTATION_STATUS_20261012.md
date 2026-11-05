# CP2 status â€” 12 October 2026

## Confirmed today
- Python suite: 514 passed; 19 existing Rasterio deprecation warnings.
- Reporting dbt parse passed using an actual source manifest.
- Isolated upcoming-bookings dbt build: 19 successful operations (15 data tests, 2 seeds, 2 views), cautious dependency selection. Earlier partial selections failed because unrelated test dependencies were absent; they are not claimed as passing full release checks.
- Cloud Build dde44c2d-ea10-4b11-99c9-da46f4ee9223 succeeded, including container import/policy smoke check.
- Reporting daily job now uses digest sha256:cc5c41724b6196aced3ee910513f4cc8a6f4ff1eef2f53b6cadb9b234217280b, one task, 20 minutes, zero retries. Release 20261012011959adc38a subsequently validated and published at 09:27:56 Malaysia.
- Future bookings are read separately for 30 local days and published only as aggregate reporting rows. Historical Calendar snapshots, outcome coverage, frozen model and protocols are unchanged.
- Overview and Sales saved default ranges corrected to current year. Warranty share committed as Percent and verified at 16.55%; absent dated refunds explained explicitly. Recurring reminders sorted chronologically, plan labels shortened and chart changed to vertical for readability. Spatial radius table moved fully into its card and fitted to data. Pest typography enlarged; stale cached frames replaced with unique upload names.
- Report access remains Restricted, owner only. No viewers added or public exposure.

## Earlier failure — recovered below
- Scheduled reporting execution cp2-reporting-daily-tpn5m failed 12 October 06:00 Malaysia time: Google read-only sign-in expired/revoked. Previous Gold release remains intact.
- Collector requests at 08:48, 08:50 and 08:52 Malaysia returned HTTP 503. Last successful collector request observed: 11 October 21:56:04 Malaysia (13:56:04 UTC). Do not fabricate missed predictions.
- Local credential refresh also failed. Renewal page was opened but timed out after 180 seconds without completed consent. User sign-in is required before publishing the future-booking source or verifying recovery.

## Recovery checklist — subsequent results below
1. Validate read-only Sheets/Calendar access, rotate the existing restricted Secret Manager token version, without changing permissions.
2. Verify an actual scheduled collector HTTP 200 and audit/protocol health; record gap/missed windows unchanged.
3. Execute reporting job, run full candidate dbt/KPI/privacy gates and publish only on success.
4. Connect Services upcoming table to approved dashboard_upcoming_appointments; remove temporary connection-unavailable note only after real bookings/coverage checks pass.
5. Finish final whole-report totals, privacy, narrow-screen and current-spending acceptance. Stakeholder viewer access requires named recipients. Prospective outcome evaluation remains future work, earliest 30 November subject to completeness.

Evidence: outputs/dashboard_design/20261012_acceptance. Dashboard is saved in native Looker Studio; do not represent the overall project as complete while collection is failing.

## Rendering acceptance limitation
At an 800 px viewport, the fixed 1600 px report scales down and small labels become difficult to read with the navigation drawer open. This is not a responsive mobile dashboard. Normal desktop viewing is the intended presentation; narrow-screen usability is not marked passed. Temporary viewport override was reset.

## Reconciled current published totals
2026 Sales RM576,670.66; packages 861; recorded scheduled visits 3,039; warranty-labelled visits 503 (16.55%). Bounded BigQuery query retained as totals_check.sql.

## Access recovery — 12 October, 09:20 Malaysia
- User completed renewed Google consent. Local Calendar credentials validated; existing restricted Secret Manager token rotated to version 3, with no permission expansion.
- Actual scheduled collector request at 01:20:04 UTC returned HTTP 200. Durable last_tick checked_at_utc advanced to 01:20:07.678777 UTC; 28 Calendar events checked, zero newly missed windows. Historical missed windows remain 38; October 10 cohort still reports one unresolved candidate and zero confirmed missed eligible windows. This does not establish complete cohort eligibility.
- Reporting retry cp2-reporting-daily-cwbls is running, audit run_id 20261012011959adc38a STARTED. Publication remains pending candidate checks.
- Chrome browser connection became unavailable; final upcoming-source connection and visual acceptance cannot currently be completed through the browser.

## Verified recovery and dashboard connection
- Reporting execution cp2-reporting-daily-cwbls completed successfully in 8m19.44s. Audit records VALIDATED 01:26:55 UTC and PUBLISHED 01:27:56 UTC, release 20261012011959adc38a.
- Real scheduled collector requests at 09:28 and 09:30 Malaysia also returned HTTP 200.
- Chrome reconnected. Native Services table now uses stable Gold dashboard_upcoming_appointments, sorted by service_date ascending, rolling today through today+13 days, cross-filtering disabled. Obsolete connection notice removed.
- Upcoming table has 12 dated rows in this window; displayed first six dates/counts match bounded BigQuery query (12 Oct 14, 13 Oct 15, 14 Oct 13, 15 Oct 10, 16 Oct 11, 17 Oct 11).
- Fresh 2026 source-to-Gold totals: Sales RM576,670.66, packages 861, scheduled visits 3,053, warranty-labelled visits 505. Dashboard cache refresh initiated for Overview.
- Remaining acceptance limits: named management viewers not yet configured (Restricted owner only); narrow-screen readability not passed; current spending receipt not verified; original/future experiment completeness still subject to eligibility and mature outcome checks, not a completed accuracy result.

## Native dashboard revision and acceptance — 12 October, 13:39 Malaysia
- All 13 static mockup image components removed; native editable text/shapes retained alongside connected charts. Per-page image audit saved in outputs/dashboard_design/20261012_acceptance/native_final/image_removal_audit.json.
- Reporting attention source corrected to dashboard_upcoming_appointments. Cloud Build b1b499d2-c4b6-459d-b342-471c0370afdc succeeded; reporting execution cp2-reporting-daily-xs4z4 succeeded in 8m19.34s. Image digest sha256:214fd25632106887f4cbc224182e6a98efb081b9580d004cce71e1691c895f33.
- Updated reconciled 2026 totals: sales RM577,668.66; 863 packages; 3,052 scheduled visits; 505 warranty-labelled visits (16.55%). Recurring contract totals: RM92,835 sales, RM25,048 recorded paid, RM67,787 remaining.
- Services pivot typography reduced to 14 px and date dimension display name changed to Weekday; recurrence chart labels shortened to day ranges. Fixed missing initial letter in Recurring payments title. Added missing Visits in shown areas label to the 2,699 area total.
- Actions filter tested: Upcoming visits selection changes 45 overall review entries to 19 team/date groups; reset verified. This is 75 bookings, not 19 customers or completed treatments.
- Weather, model, quality, package and area pages loaded and reviewed. Model experimental status, 94% versus 95% baseline, five-positive limitation, and future outcome dates remain visible. No private customer identifiers displayed in reviewed report fields.
- Narrow check repeated at 800 x 900 after native report width changed to 1400. Whole overview fits, but detailed tables scale small; desktop remains recommended. Viewport override reset. This is not claimed as a responsive mobile layout.
- User requested open link access rather than named viewers. Sharing dialog remains Restricted; action-time confirmation requested for Unlisted (anyone with link), not searchable Public. No access expansion applied yet.
- Some chart labels remain abbreviated at narrow widths. Final full-report visual acceptance and current spending receipt are not declared complete. Future cohort completeness/outcome evaluation remains pending.

## Confirmed link access and small-screen readability — 12 October
- User explicitly confirmed anyone-with-link viewing. Saved Unlisted / Viewer, reopened sharing dialog and verified Anyone on the internet with the link can view. Searchable Public was not selected. Evidence: native_final/link_access_enabled.png.
- Native Looker conversion dialog states existing freeform reports cannot directly convert to responsive; a separate responsive report must be created and components copied for automatic reflow.
- Set report display mode to Actual size and navigation to Tab. Tested 800x900 and 390x844: text no longer shrinks to fit; horizontal scrolling reaches offscreen components. This is a readability improvement, not a fully responsive stacked phone layout. Temporary viewport override reset.
- Evidence: overview_800px_readable.png, overview_390px_readable.png, dashboard_actual_size_final.png. Saved dashboard left open.

## Dashboard hierarchy improvement — 12 October
- Added a short purpose/decision guide beneath each of the 13 native page titles, explaining what to review first and relevant limits.
- Overview directs attention to sales, bookings and warranty visits, and flags the incomplete October period. Added readable white context inside the navy Sales card: package prices, with contract balances reviewed in Recurring payments.
- Preserved connected charts, source totals, experimental model caveats and link Viewer sharing. No static image components added.
- Evidence: native_final/design_hierarchy_overview.png. This revision improves guidance and contrast; it does not claim an automatic responsive phone layout.

## Mockup-inspired visual revision — 12 October
- Revisited the original page_01_frame.png reference. Applied pale #f4f5fa report background, white component surfaces, navy #172b4d primary/chart-title colour and rounded surfaces via native theme.
- Removed oversized outlined title-banner shapes from all 13 pages, retaining editable titles and purpose lines on the pale page background.
- Added a native white panel grouping the Overview sales heading and chart. Preserved navy Sales highlight and readable white payment-context text. Removed theme-wide nested component borders after visual review.
- Evidence: native_final/mockup_style_overview.png. Data definitions, connected sources and Viewer link access unchanged.

## Wording, spacing and layout refinement — 12 October
- Standardized all 13 page titles to bold 32 px navy, concise 18 px grey subtitles and bold 20 px section labels. Shortened the Model comparisons title and simplified page-purpose wording.
- Removed repeated blank lines from explanatory notes; retained source definitions, limits and model evidence. Native note text uses 18 px where appropriate; Overview's single-line business definition is 16 px.
- Corrected the Overview chart-panel height from 500 to 447 px, removing overlap with the KPI row. Verified top and bottom screenshots at normal viewing size.
- Evidence: native_final/spacing_wording_overview_top.png and spacing_wording_overview_bottom.png. No analytical values, sources or sharing permissions changed.

## Approved green mockup implementation — 12 October, in progress
- Rebuilt the live Overview using compact green/white KPI cards, native monthly sales, horizontal team bookings, reminder attention cards and paid/remaining contract cards. Added an October-incomplete sales heading.
- Recurring payments: compact KPI row, reminder date table, native paid/remaining chart by plan, missing-date table and concise payment definition. Styling uses #19342d, #21765d, #71817a, #e9f3ed and #f5f6f2.
- Services: corrected the actual service_date chart aggregation from Date to Day of Week (not merely its display name). Native matrix now shows Sunday–Saturday. Horizontal green team chart and top KPI row implemented.
- Simplified page titles/notes across all 13 retained analytical views. Model remains experimental; 4/5 top-20 capture, 16 false alerts, 1 missed, 94% vs 95% baseline and future-test dates remain visible. Model hero is now mint with readable ink text.
- Nine top-level navigation subjects now exist: Overview, Sales & enquiries, Services, Warranty, Pests & packages, Areas & weather, Recurring payments, Model results, Data checks. Four sections contain related detail pages, preserving all 13 source-backed views. No pages were hidden. Empty pages accidentally created while adding sections were removed through normal recoverable UI operations.
- Live report remains 590914e8-066b-4671-a130-7a62a3af435a; Chrome tab 942980864 (old 942980854 no longer exists). Sharing unchanged.
- Current viewer proofs: outputs/dashboard_design/20261012_redesign_live/overview_desktop.png and model_desktop.png. These are intermediate; final acceptance not complete.
- Still to finish: child-page ordering (Areas before Weather, Held-out before Model comparisons, Quality before Actions); complete viewer checks including lower sections, final screenshots, filter-reset checks and narrow-screen rendering. Some chart palette/geometry still differs from approved HTML mockup. Native payment chart currently uses a stacked bar plus balances rather than a donut. Do not claim pixel-identical implementation or mobile reflow.
- Looker conversion dialog again confirms existing freeform report cannot directly switch to Responsive. Left navigation + Fit to width applied. No new responsive report created.
- Official documentation confirms hidden pages cannot be reached via links; therefore retained details are grouped, not hidden.

## Desktop-only design polish (latest user direction)
User deferred responsive/mobile layout; original report remains the deliverable. Private responsive draft is incomplete and is not the live dashboard.
Applied to original report: monthly sales range now follows available data (Jan-Oct), compact axes; Overview and Services team bars use horizontal labels and data labels; recurring reminder and missing-date tables use theme mint headers and larger row labels; Services and Pests package KPI labels no longer misleadingly red; warranty share heading moved above its scorecard to remove overlap and main warranty KPI resized; pest matrix headers wrap with smaller type. Original Overview totals remain RM577.67K, 863 packages, 3,052 bookings, 505 warranty visits. Model proof refreshed, experimental caveats retained. Original sharing unchanged.
Proofs: outputs/dashboard_design/20261012_redesign_live/overview_desktop.png and model_desktop.png. Desktop polish is applied; do not claim pixel-identical mockup or full project acceptance. Some long source category labels and wide matrices still warrant further refinement.
