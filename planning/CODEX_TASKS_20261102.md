
## H. Return-visit risk score (added 3 November, updated 4 November by Claude)

Story: `planning/CP2_PRESENTATION_STORY_20261103.md`. Study: `outputs/model_validation/20261103_return_risk/Summary.md` (write-once; `scripts/research_return_risk_20261103.py`). Test May to Oct 2026 (1,270 services, 108 returns): AUC 0.81 (0.77 to 0.85); top 20% reaches 62% of returns vs 52% for the final-residential rule and 21% random; monthly totals about 17% low.

Built and tested (tests/test_return_risk.py, 12 tests):
- `webapp/return_risk.py`: scores with the frozen `webapp/models/return_risk_v1.json` (identical to the study, max diff 1e-16), builds the weekly check-in plan (`plan`), validates the runtime file `return_risk_predictors.json` (model inputs only, outcome columns refused), and records check-in results (`record`, `outcome_summary`).
- `GET /api/return-risk?calls=N` returns the plan plus `revision`, `log_available`, `done` and `outcomes`. `POST /api/return-risk/outcome` {sale_id, serviced, status: no_issue | issue_found | visit_booked | no_answer, note, revision} writes to the existing action ledger under a sha256 key (`checkin|sale|date`, fits the current key rule). Reached customers drop out of the plan; "no answer" stays in it.
- Portal: Return-visit risk page has the plan with a calls slider, a result form per customer and a check-in log; Today shows the top 5 when live.
- `webapp/storage.py` pulls `return_risk_predictors.json` (optional, validated, last-good kept). `scripts/publish_return_risk_predictors.py` publishes it from an export (`--export`) or from a reporting run folder (`--run-dir`, `from_release`).
- `scripts/cp2_reporting_release.py` `finish_release` calls `from_release` after the portal export only when `CP2_RETURN_RISK_PREDICTORS=yes` (default off; failures are written to `return_risk_export.json` and never touch the release).

For Codex (needs GCP access):
1. Make live scores daily. `from_release` reuses `callback_live_features.derive` (read-only, session temp tables, own folder `return_risk_features/` in the reporting run). The reporting image does not yet carry its inputs: `callback_live_features.py`, `benchmark_warranty_models.py`, `freeze_callback_prospective.py`, `refresh_callback_validation.py`, `config/cp2_model_current.json` with the bundle, `config/cp2_live_feature_contract.json`, compiled dbt SQL and the 27 September baseline calendar. Either add them to `Dockerfile` (hydrate the private baseline like the collector does) and set `CP2_RETURN_RISK_PREDICTORS=yes`, or run `publish_return_risk_predictors.py --run-dir ... --uri $CP2_PORTAL_GCS_URI` as a separate job in the collector image. Do not change the collector, its configs or ledger.
2. Deploy the portal (Cloud Run) so the check-in log uses `CP2_ACTIONS_GCS_URI`.
3. Declare the pilot before scoring: for two to four weeks, alternate weeks (or half of the plan by random draw) get calls; compare 30-day returns between called and not called. Check-in results in the action ledger carry `chance_at_save`, `day_of_window` and `model_version` for that analysis.
4. Optional: a "high-risk job" flag on the booking calendar needs a link from a scheduled appointment to its sale; not available in the runtime files yet.

The frozen pest-return experiment and the 30 November evaluation are unchanged.

## Deadline update (4 November): everything finishes on 30 November 2026

The whole project, report and logbook are due 30 November (not 24 December). Dated order:

| By | Task | Notes |
|---|---|---|
| 9 Nov | Deploy the portal (Task D in `CP2_REMAINING_TASKS_20261102.md`) with the 4 November code | Includes `webapp/models/checkin_pilot_v1.json`. Check `/api/return-risk` returns `pilot` and that `CP2_ACTIONS_GCS_URI` is set so check-ins persist |
| 9 Nov | Daily predictor export live (Task H step 1) | The pilot starts 10 Nov and needs current services in the plan; if the reporting image cannot be extended in time, run `scripts/publish_return_risk_predictors.py --run-dir ... --uri $CP2_PORTAL_GCS_URI` daily as a separate job |
| 10 to 23 Nov | Check-in pilot runs (protocol `planning/CP2_CHECKIN_PILOT_PROTOCOL_20261104.md`, SHA-256 of the config `84921e56b8f35e9fcd7dbe20b341b389e2505482e80313c5672799a717ce32a1`) | Do not edit the config; a change needs a new pilot id |
| 24 Nov | Export the action ledger and run `python scripts/evaluate_checkin_pilot.py --ledger <state.json>` | Process measures only; save output under `outputs/model_validation/20261110_checkin_pilot/` |
| 27 to 28 Nov | Warranty-risk forward record (Task E) | The 2 November independent review found this record was created after part of its outcome period started; if run, label it a retrospective check, not a prospective test (report Section 4.29) |
| 30 Nov 14:00 and 15:00 MYT | Pest-return and recovery evaluation (Task F), unchanged | Hand the result or the rejection reason to Claude the same afternoon |

The customer-initiated return comparison of the pilot matures from 14 December, after submission; it is reported as declared and maturing.


## Dashboard split (4 November, Claude)

Descriptive charts (sales, visits, payments, collection) belong in the business dashboard; the website keeps only model and planning charts. Done in code: the Performance page no longer draws monthly sales or contract collection and links to the dashboard instead; the Business dashboard page has one "Open the dashboard" button (the `/reports` link was removed from the page, its route is unchanged). The dashboard address is one setting: `CP2_DASHBOARD_URL` (https only). Unset = the existing Looker Studio report, embedded as before. When Metabase on Oracle is live with HTTPS, set `CP2_DASHBOARD_URL` to its dashboard address on the Cloud Run service; it opens in a new tab rather than being embedded, so no CSP change is needed. Test: `tests/test_return_risk.py::test_dashboard_link_defaults_to_looker_and_accepts_only_https`.

## UI and data update to deploy (4 November, Claude)

- Website: light-blue header cards, one colour per chart series, new **Prediction models** page (`#models`, management view), menu group "Predictions" (Prediction models, Technical evidence); Warranty-risk research removed from the menu (route kept). Booking calendar: plain-language intro, tabs "Find a time slot", "Google Calendar", "Weekly workload"; suitable slots green, backup amber. All website JavaScript and CSS reformatted for readability (Prettier, no behaviour change).
- Google Calendar tab: set `CP2_GOOGLE_CALENDAR_IDS` (comma-separated calendar IDs of the six team calendars) on the Cloud Run portal service. CSP now allows `frame-src https://calendar.google.com`. Without the setting the tab shows an "Open Google Calendar" button only. The embed shows events only to a viewer whose Google account can see those calendars.
- Data: `webapp/business.py` now groups the 144 free-text Sales pest spellings into 23 standard categories (`pest_group`). It runs inside the reporting job's business export, so rebuild the reporting image as well as the portal.
- Tests: 783 pass on the full checkout plus 3 in `tests/test_portal_links.py`. Retest evidence: `outputs/model_validation/20261104_return_risk_retest/`. Clean-up notes: `planning/CP2_CLEANUP_NOTES_20261104.md`.

## Monitoring, capacity, customer filters, dashboard pest groups, failure alert (4 November, Claude)

Oracle/Metabase is ON HOLD (owner decision, 4 November). Keep Looker Studio.

Built and tested (788 Python tests plus both UI checks pass on the full checkout; checked in a browser against the 4 November runtime):
- **Monthly model check.** `scripts/monitor_return_risk.py --labels <matured label export> --uri $CP2_PORTAL_GCS_URI` writes `return_risk_monitor.json`; the portal pulls it (validated, last good kept) and shows it on Prediction models. Uses only complete months whose services have all passed day 30. Status "ok" when the last three complete months have AUC at least 0.70 and recorded/expected between 0.8 and 1.25; it also reports a count factor for planning totals (ranking unchanged). Run monthly after the matured-label export; current result (1 Nov data): ok, AUC 0.84, factor 1.15. Copy at `outputs/model_validation/20261104_return_risk_retest/return_risk_monitor.json`.
- **Weekly capacity suggestion** on the Workspace page: next week's hours forecast plus its usual miss as buffer, and the share of a typical week spent on return visits; compares with the saved team capacity when one is set.
- **Customer history**: Show filter (all, repeat, one programme, identity needs review), Order by (sales, programmes, name) and a summary row. `/api/customers` accepts `relationship` and `sort`.
- **Dashboard pest groups**: new macro `dbt/macros/pest_group.sql` and Gold view `dashboard_sales_pest_groups` (sales by month and standard pest group). The pinned `gold/sales_package_facts.sql` is NOT changed (it is hash-pinned by the frozen feature contract). Run `dbt build --select dashboard_sales_pest_groups` with the release variables, then point the Looker pest charts at it. A test keeps the macro's keywords identical to the website's.
- **Failure alert**: `infra/alerts/` has the Cloud Monitoring policy and two gcloud commands (email channel, policy). It fires on a failed `cp2-reporting-daily` execution or 26 hours without a success.

## 5 Nov 2026: Hallmark redesign (design system only)

- Portal stylesheet redesigned with Hallmark, brand theme "Nomobug Clear" (layout order, wiring and wording unchanged; phone-width fixes). Evidence: `outputs/website_design/20261105_hallmark/`.
- Headings use the existing Archivo font (`/archivo.woff2`); body stays Instrument Sans. `chivo-mono.woff2` and its `/chivo-mono.woff2` route in `webapp/server.py` are no longer used and can be removed.
- Chart colours now come from CSS tokens (`--chart-*`) in `style.css`; edit colours there, not in the JS.
- Deploy: ship with the next portal deploy, no config needed. Please stage and rebase before editing `style.css` or `stages.js` again.

## 5 Nov 2026: Management overview (portal)

- New first page `#overview` (Management overview): headline sales, the week's top 5 actions with reasons and "see why" links, top 5 areas, package performance. Built in `stages.js` (renderOverview) from `/api/analytics`, which now also returns `packages` and `areas` from the new `webapp/overview.py` (plain counts, no trained model). Tests: `tests/test_overview.py`.
- Booking page renamed "Bookings & workload": shows the weekly workload forecast and the Google Calendar tab only. The slot finder (`renderBookingTools`, `/api/booking/options`) stays in the code but is no longer shown, because staff plan travel and slots in Google Maps and Google Calendar.
- Deploy with the next portal deploy; no new config. Report and logbook: describe the overview as the management view and the slot finder as a prototype that was retired after staff feedback.

## 5 Nov 2026 (Claude): pilot cancelled, model tables for Looker, deploys

- **Check-in pilot not run** (owner decision). The 10 to 23 November pilot and 24 November evaluation rows in the deadline table no longer apply. See the decision at the end of `CP2_CHECKIN_PILOT_PROTOCOL_20261104.md`.
- **Portal** revision `cp2-portal-design-1105c` serves 100% (overview wording, readable addresses `#workspace` `#follow-up` `#reminders` `#bookings`, sales chart removed from overview, loading text, AI assistant retired). Traffic now follows the latest revision.
- **Model results in BigQuery** for Looker: dataset `predictions` (`return_risk_scores`, `return_risk_call_list` view with names, `booking_forecast`, `forecast_backtest`, `staffing_plan`). Written by `scripts/publish_prediction_tables.py`, called by the daily reporting job when `CP2_PREDICTION_TABLES=yes` (set). The reporting job account has WRITER on this dataset only. Reporting image `3a5b96a5`.
- **Looker build plan**: `outputs/dashboard_design/20261105_looker_predictions/index.html` (5 pages, table and field per card).
- **New inputs study**: team, job timing and sales context did not improve return_risk_v1. `outputs/model_validation/20261105_new_inputs/Summary.md`.
