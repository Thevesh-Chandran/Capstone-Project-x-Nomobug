# Approved dashboard implementation — 15 October 2026

Owner priority: implement the mockup's layout and exact chart types before cosmetic detail. Website refinements paused at owner request. No illustrative mockup values may be published as business figures.

## Main navigation

Seven primary sections: Overview; Sales & customers (Sales and Customers subviews); Enquiries; Services & warranty (Services and Warranty subviews); Pests & packages; Areas & weather (Areas and Weather subviews); Payments. Keep Data checks as supporting reporting, and preserve old model evidence without deleting it. Original 14 content pages remain; temporary empty pages created during grouping were removed. The old Model results section is hidden in viewer navigation; the website has model evidence and area checks.

## Layout and source binding

| Main view | Mockup layout / charts | Approved sources |
|---|---|---|
| Overview | Four headline cards; wide monthly Sales + Packages combo chart; district sales horizontal bars; package count bars; compact source-backed attention table | sales_monthly_recorded; dashboard_business_sales; dashboard_package_fit_matrix; dashboard_attention |
| Sales & customers | Sales trend, sales/customer breakdown, repeat programme mix and group totals; all-history customer scope separately labelled | sales_monthly_recorded; dashboard_business_customers |
| Enquiries | Monthly trend, recorded status/source breakdown, contextual payment links; no unsupported conversion | prospect_reply_monthly_recorded; dashboard_payment_link_monthly |
| Services & warranty | Visit cards, team/date heatmap, team booking bars, daily trend and upcoming visits; formal claims separate from Calendar signals | dashboard_service_monthly; dashboard_team_workload; dashboard_scheduling_capacity; dashboard_upcoming_appointments |
| Pests & packages | Package/pest sales bars and package × pest comparison; missing category labels retained | dashboard_package_fit_matrix |
| Areas & weather | District ranking and coverage; rainfall and humidity comparison panels with their correct units | dashboard_business_sales; dashboard_weather_monthly; spatial cluster sources |
| Payments | Contract/paid/balance/reminder cards; reminder schedule; paid-versus-remaining bars by arrangement; missing-date detail; refunds only where verified dated rows support a chart | dashboard_recurring_payment_quality; dashboard_recurring_reminder_schedule; dashboard_refund_monthly |

Heatmap periods: day, week and month from `service_date`, `week_start`, `month_start`, with team rows and booking counts. Published `gold.dashboard_team_workload` derives from the stable approved scheduling view; it follows future releases without date-pinned source tables. Reconciled: 3,074 bookings, six Calendars. There is no verified structured individual-technician field, so team names must not be presented as individual technicians.

Calendar records are bookings, not completed work, utilisation or available capacity. Recurring balances use SALES; green dates merely elapsed, and reminder dates do not establish sent reminders or unpaid instalments. Do not infer profit from sales or reduce sales automatically by unallocated refund entries.

## Current verification

- Website revision cp2-portal-00013-m9l deployed with two experimental planning tools; private access unchanged. Later local source-freshness guard is not in that revision yet; website refinement is paused.
- Portable repeat-model inference reproduced all 557 test scores. Current tools are planning estimates/priority lists, not a new prospective outcome study. Existing pest-return v5 hashes and collection protocol are unchanged.
- Report grouping and Payments rename saved. The full graph/layout transformation remains in progress; do not claim exact mockup match or final acceptance.
- Controlled navigation by page URL can trigger a blank Google/reCAPTCHA state. The owner restored the editor by normal Chrome reload. Use the report's own navigation thereafter; do not bypass verification.
- New custom colours require real keystroke input and an observed RGB update before Done; a programmatic fill alone did not commit the colour. A temporary wrong page colour was reset, then Payments pale background was visibly verified.

### Overview editing checkpoint
- Monthly chart converted to combo: Sales (RM) bars on left axis and countable_package_rows line labelled Packages sold on right axis; legend enabled; ascending month sort retained.
- Lower-left chart now dashboard_package_fit_matrix, package_type dimension, SUM(package_rows), descending package_rows sort. Heading changed to Packages sold. This source is 2026-only and has no date dimension; selected-date interaction must be made explicit or replaced by a date-grained approved source before acceptance.
- District bar and attention table placement remain unfinished. Existing reminder and contract-balance cards are retained meanwhile.
- Settings survived an owner reload. Newly changed chart iframes remain about:blank; browser logs recorded Data Studio System Error / Data request rejected (5acf32da). Source/renderer diagnosis is still required; no successful visual rendering is claimed. Do not infer that this is only a CAPTCHA problem.
- Proof: outputs/implementation/20261015/overview_editor_checkpoint.png. This is an unfinished editor checkpoint, not final dashboard acceptance.

### Verified Overview refinement
- Combo chart rendered with Sales (RM) bars and Packages sold line, separate axes and correct month labels.
- District bar added using Sales by area. Refreshed connector schema: month_start and source_release added with no connection configuration change. Applied the existing 2026 sales — assigned districts filter and bound date-range dimension month_start. Chart-specific District label strips only the state prefix. Top five assigned districts plus Others, all assigned areas retained in aggregation. Expanded left plot margin to make names readable. No unknown locations were allocated to districts.
- Package bars switched to dated Sales by area with package dimension and SUM(sale_rows), date dimension month_start and descending count. This fixes the earlier missing-label and date-control problem. Governed Unspecified category remains. Top five plus Others totals 878 in the default 2026 scope.
- Replaced duplicate Overview recurring cards with current payment-arrangement table: Sales recorded paid, reminder contracts next 7 days, missing schedules. Wrapped headers and rebalanced column widths; no client names or contacts. Values verified: reminder counts 2 quarterly + 5 monthly = 7; missing schedules 2 deposit + 7 after each treatment + 1 every four months = 10. This is current snapshot scope, not historical cash flow.
- Viewer rendering inspected. Proof overview_refined_top.png. Services weekday/team pivot and booking trend render, but day/week/month selector implementation is in progress.

### Owner-requested handoff
Owner asked to stop dashboard editing and provide a guide after the current chart.
- Services: removed the separate dimension controller after it failed isolation. Original weekday/team pivot is rendered and restored. Added dashboard_team_workload connector and bound booking trend to SUM(bookings), date filter service_date. Native drill hierarchy includes Month (Year Month), Week (ISO Year Week), service_date, with auto-added broader Year/Year Month levels. Viewer tests: monthly Y max 400, weekly Y max 150, daily Y max 30; original team heatmap unchanged. Returned to Month after testing. Enlarged trend height and renamed heading. Proof services_daily_verified.png and services_monthly_verified.png.
- Payments: existing Paid (RM) + Remaining (RM) chart has been changed to horizontal stacked bars. Source dashboard_recurring_payment_quality unchanged. Expanded inner left plot margin for arrangement labels. Native Refresh data requested once; frame still blank, so rendering not verified. No claim of finished chart/report.
- Rewrote planning/CP2_DASHBOARD_BUILD_GUIDE.md as the current 15 October practical handoff. It supersedes older instructions about PAYMENTS tracking, prospective dates and payment-source deployment. Website refinement remains paused. No permission, model, collector or source-sheet changes made during this dashboard work.
