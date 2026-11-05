> Update — 1 November 2026: the user removed the generative AI assistant. Ask Nomobug and the Ollama runtime are retired. The visual booking calendar, source-backed work summaries, reporting and predictive-model research remain. Earlier AI descriptions below are historical.

# Nomobug decision workspace — 25 October 2026

## Current implementation — 30 October

**Booking extension:** Plan now has Find a booking option and Weekly demand tabs. The booking form searches customer appointments, checks the staff-supplied working period and duration against the six-Calendar schedule, and presents usual-team, cross-area or backup options. Availability notes, meetings and breaks remain blocks and cannot be selected for removal. Only the explicit customer appointment selected for rescheduling is omitted from that scenario. Working-hours, break and service-suitability assumptions require staff confirmation; changing the form clears that confirmation.

The private booking feed was verified against the original immutable Bronze content hash and published with its actual capture time, **30 October 06:01 MYT**. It contains 326 blocking events, including availability blocks, and 212 recognised customer appointments eligible for search. It is independent of financial Gold promotion, contains no descriptions/addresses from Calendar, and expires after 36 hours. Future daily reporting attempts export it after the complete source load and before programme reconciliation. The updated job image has been installed; its next natural scheduled export is still pending verification.

This is a constraint-based Calendar-fit tool, not a newly trained model. Travel allowance is staff-entered, road travel is unverified, no staff availability has been independently confirmed and no booking is written back to Google. Customer-renewal workflow is still pending. Full Python suite: 706 passed; final booking/storage/reporting/workspace checks: 45 passed. Live browser checks cover backup options, customer search and consultation-only team selection. Financial reporting remains stale as described below; the independent booking capture time is shown separately.

The website now groups daily use into Work, Plan and Customers & areas, with Dashboard and Evidence separate. Customer records and maps share contextual navigation. Plan leads with a source-gated next decision and a visual comparison of forecast full-week appointment hours with staff-entered available hours. It shows upcoming-day booking concentrations, preserves separate one-week hours and two-week booking horizons, labels unsaved scenarios and exports the saved decision with its assumptions. Task-focused assistant briefs use the same decision logic and link to the relevant workspace.

The end-to-end source/API checks pass against the retained reporting release. The reporting refresh itself is blocked: the 30 October candidate lacks the previously reviewed CONTRACT_0002 stage-13 Calendar event, failing the reviewed-visit and programme-count invariants. The published source timestamp remains 28 October; the new decision panel correctly refuses a current capacity recommendation. No missing appointment was invented or silently removed from the quality gates. This source discrepancy needs resolution before claiming fresh operational planning.

The earlier workspace-only release passed 685 Python tests, followed by 13 workspace checks after its final assistant wording update. Browser access was subsequently restored for the booking extension checks above. Model accuracy and business adoption are not established by these interface changes.

## Purpose

### Booking and customer-renewal extension

User priorities confirmed 30 October: choosing teams/times for new or rescheduled bookings, and supporting customer renewals. Canonical team preferences are recorded in `config/cp2_team_coverage.json`, matched to the six existing Calendar names. Areas are soft preferences: try the regular team, then evaluate cross-area cover against actual appointment conflicts, travel and staff-supplied working hours. Sales is consultation-only; Beast is currently inactive; Replacement covers KL/Selangor as backup. Inactivity applies to new recommendations and never deletes historical activity.

The territory configuration alone is not a scheduling engine and does not establish free time, treatment capability, travel duration or completed treatment. Do not infer those from a team's daily booking count. Renewal follow-ups must distinguish separate paid programmes from upsells, warranty visits and duplicate Calendar numbering. A future renewal classifier must outperform a declared simple rule on valid later records before its scores guide staff.

Turn source records and experimental forecasts into staff work: inspect the evidence, decide the next step, prepare the work and record progress. Looker remains the aggregate reporting surface. The private website provides the controls and investigation flows that reporting does not perform.

## Main flows

- **Operations desk:** source-backed reminder dates, missing details and contract-status checks → review drawer → inspect the exact customer/sale → edit/copy a message draft if appropriate → save team progress.
- **Weekly planner:** current/next week selector → confirmed future Calendar booking-count heatmap by team/day → matched, timely booking/hour forecasts when available → staff-entered whole-week appointment-slot capacity and optional buffer → save the plan and download a working brief.
- **Ask Nomobug:** task buttons and supported task questions produce immediate verified briefs with working links. Broader questions continue through the existing source-backed Ollama path. Verified briefs are labelled as such rather than represented as generated forecasts.
- **Area intelligence:** investigate recorded sales and pest-return patterns, then inspect underlying records. Customer search, maps, reporting and research evidence remain available.

## Metric/action contract

| Signal | Grain / period | What staff can do | Guardrail |
|---|---|---|---|
| Reminder dates to review | Contracts with a positive recorded balance and a source date in the next 7 Malaysia calendar days | Verify Sales, review agreement, prepare a message | Dates do not establish an overdue instalment, payment received or message sent |
| Details to confirm | Contracts with missing dates, unknown balances or an explicit cancellation/relocation name annotation | Check the source and confirm contract status | Cancellation note blocks the automatic payment draft; it is not assumed to cancel the contract or clear its balance |
| Reviews recorded | Internal staff progress for the current review items | Reopen, record checked, waiting, or contact logged manually | Does not settle cash or prove delivery; changed evidence reopens review |
| Advance bookings | Confirmed Calendar bookings by team/day within selected week, from today onward | Confirm appointments and discuss roster distribution | Booking count is not available capacity, completed treatment or technician productivity |
| Two-week booking forecast | Fixed selected model, exact logged origin/horizon | Review incoming booking demand alongside the weekly plan | Do not apply it as a one-week hour forecast; historical evidence is separate |
| One-week appointment hours | Fixed selected model, exact logged origin/week | Compare full-week appointment-slot capacity plus a staff-selected buffer | Never apply another week's forecast; no invented current prediction or calibrated interval |

## Persistence and privacy

Internal notes, review statuses and weekly capacity assumptions are stored in a separate private bucket, `cp2-workspace-private-profound-keel-500007-s4`. Only the portal runtime receives object-user access there; its reporting snapshot access stays read-only. Google source scopes and IAP access stay unchanged. Writes use object-generation preconditions so staff updates cannot silently overwrite each other. Staff identities are pseudonymized from an already validated IAP subject. The ledger is bounded to 1 MiB / 1,500 items; reaching the bound stops writes and requires an explicit archival workflow.

The production prefix is `team`. Acceptance checks use `acceptance-20261025`; those test notes and capacity inputs are not shown in production. A hosted instance without the durable-store configuration refuses progress writes. No external messages are sent, no payments are marked paid and no Calendar/Sheets records are edited.

## Model integrity

Frozen pest-return weights, thresholds, cohorts and receipts are unchanged. Forecasts are not backfilled or moved to another horizon. Before 26 October, the planner reports that the new weekly test has not issued a forecast; it does not substitute historical predictions. Model performance is not improved by this interface redesign. The improvement is a usable, auditable decision workflow around the evidence.

## Operating evidence

See `outputs/workspace_rebuild/20261025/` for current tests, cloud release records and desktop screenshots. The forthcoming natural forecast run remains independent of website use.

## 25 October acceptance

The decision workspace passed **669 Python tests**, JavaScript syntax checks, and the website/reporting container smoke builds. Browser checks at 1440×1000 covered source counts, a review drawer, full customer-history handoff, a saved note surviving a full reload, a saved/exported weekly planning brief, the current/next-week selector, pre-test forecast wording, cancellation-note draft blocking, exact currency display and navigation resetting to the page heading. No browser console errors were observed.

Acceptance writes used only `acceptance-20261025`. The final production prefix `team` was verified empty: zero recorded reviews and no invented available-hour budget. An invalid Google IAP assertion was rejected on the new private workspace API. The original frozen bundle and model-pointer hashes remain unchanged. The weekly forecast trigger remains enabled for Sunday 23:50 Malaysia time; this acceptance does not claim that a future natural trigger has already succeeded.

The new upcoming-booking export was read from the existing approved Gold view under the 100 MiB/query cap and delivered within the same source release. The daily reporting image was updated so future exports retain this feed. No dbt model/warehouse metric definitions were changed in this workspace redesign. Privacy information was updated to disclose internal review notes and planning inputs in their separate private store.

Live portal revision: `cp2-portal-00058-fof`, image `portal:a1d5acc8-ed62-419d-a646-58ab4092e4a8`. Website-only build: `a1d5acc8-ed62-419d-a646-58ab4092e4a8`; daily export build: `c465152d-e2df-4237-9135-4b36f68ec3d8`; public information build: `e04a492a-0f33-4c35-ac29-ff7c6aadb593`. Prior live revision `cp2-portal-00049-6mv` remains available for rollback.
