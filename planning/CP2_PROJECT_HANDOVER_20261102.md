# Project handover, 2 November 2026

For anyone continuing the work. This covers the portal redesign, the new sign-in, the Recommendations and Performance pages, the model search, the new warranty-risk model and its forward test.

## Boundaries: what was NOT changed

- The frozen 30-day pest-return experiment: `config/cp2_model_current.json`, cohort configs, the cloud collector (`scripts/cp2_cloud_collector.py`), the prospective prediction ledger, thresholds and `scripts/evaluate_matured_cp2_subset.py`. The 30 November evaluation is unaffected.
- Data pipeline, dbt, BigQuery, Looker report, Cloud Run jobs, `webapp/booking.py`, `webapp/workspace.py`, `webapp/predictions.py`, `webapp/planning.py`, `infra/` (including the development workspace's `infra/metabase`).
- Nothing was deployed. The live Cloud Run portal still runs the previous revision.

## 1. Portal redesign (`webapp/static/`)

- One stylesheet, `style.css` (plus `maps.css` for the map page). Removed the old layered sheets: `workspace.css`, `crm.css`, `refinement.css`, `guide.css` (and two interim files from this session, `bi.css`, `bi.js`, `analytics.js`).
- Theme: black, white and cobalt (`#000`, `#fff`, `#1F4FE0`) on a cool canvas `#F3F5F9`. Font: Archivo variable (self-hosted `archivo.woff2`, OFL licence in `archivo-LICENSE.txt`). Expanded width for page titles and key figures. One cobalt block per decision page; rules and whitespace instead of rows of cards; sentence-case labels; no all-caps eyebrows, middle-dot separators or arrow glyphs on the new pages; no em dashes in interface text.
- Navigation (sidebar, black rail), plain functional groups:
  - Management: Recommendations (`#decisions`, landing page), Performance (`#performance`)
  - Operations: Follow-ups (`#home`), Scheduling (`#plan`), Payments (`#payments`)
  - Analysis: Dashboard (`#dashboard`, Looker), Models (`#status`), Warranty risk (`#risk`, new), Model accuracy by area (`#areas`)
  - Customers & areas: Customers, Area explorer (`#business`), Heatmaps (`/maps`)
- `shell.js` (new): sidebar state, breadcrumb, page title. `stages.js` (new): draws Recommendations, Performance and Warranty risk with plain SVG charts (no inline style attributes; the strict CSP is unchanged).
- Tool views (`tools.js`, `workspace.js`, `booking.js`, `maps.js`, `app.js`) keep their behaviour; only colours, chart sizes, a CSP-violating `style` attribute and link labels changed. Heatmap colours moved from a rainbow ramp to a blue ramp.
- A design canvas with mockups (Recommendations, Performance, Sign in) also exists in the user's claude.ai artifacts; the code above is the implemented version.

## 2. Sign-in (`webapp/server.py`, `index.html`, `app.js`)

- Username and password form. With no `CP2_PORTAL_TOKEN` (local runs), credentials are `admin` / `admin`. When the token is set it becomes the password; `CP2_PORTAL_USERNAME` sets the username (default `admin`). The legacy `{"token": ...}` request still works.
- A session is now always required in staff-code mode (previously no token meant open access). IAP mode is unchanged. Remote hosting still refuses codes under 24 characters.
- `/maps` redirects to `/` when signed out.

## 3. Recommendations and Performance (`webapp/analytics.py`, `GET /api/analytics`)

- `analytics.py` (new) builds descriptive aggregates, predictive context, generated options, option scoring and a performance scorecard from the private business snapshot, saved planning evidence and existing models. Authenticated; same release checks as other business endpoints.
- Recommendations: the top recommendation (cobalt block), current position, ranked options with adjustable weights (value, confidence, urgency, ease), the evidence behind each option, a capacity scenario and an action plan.
- Performance: scorecard against benchmarks (on track / watch / off track), actual vs expected monthly sales, forecast accuracy per week, follow-up progress, contract collection.
- Targets (10% repeat rate, 15% warranty ceiling, 50% collected) live in `webapp/performance_targets.json` with status `placeholder`; the page labels them "target to confirm with the owner" until `status` is set to `confirmed` with `confirmed_by` and `confirmed_on`. No owner values exist yet.

## 4. Model search (`planning/CP2_OPERATIONAL_MODEL_SEARCH_20261102.md`)

- Weekly forecasts (bookings, warranty visits, paid visits, sales count, sales value): 28 configurations each plus 4 baselines; none beat a 13-week moving average on held-out weeks.
- Repeat-purchase timing (survival analysis, 51 configurations): C-index 0.764 vs deployed repeat90 0.773, a tie.
- Selected: **property warranty risk** (`warranty_risk_v1`): after a paid visit, will the property need a warranty visit within 30 days? Extra Trees on the property's own visit history, Platt-calibrated. Held-out test (May to Sep 2026, 1,104 visits): AUC 0.77, AP 0.30 vs base rate 0.10, top 20% of visits held 52% of warranty calls, 107 calls expected vs 107 recorded. Simple rule AUC 0.55.
- Portal: `webapp/warranty_risk.py` scores open windows; new Warranty risk page; new Recommendations option "Check in early with N high-risk properties".

## 5. Forward test of warranty risk (started 2 November)

- Frozen record: `outputs/model_validation/20261102_warranty_risk_prospective/freeze_20261102T033350Z.json` (+ `.sha256`). 149 open windows from the 28 October snapshot, 9.22 warranty visits expected, 14 high-risk. Properties are stored as coordinate hashes, never names. Write-once; never overwrite.
- Label: a warranty visit at the same property after 28 October and on or before each window end. Last window ends 27 November.
- Evaluate with a snapshot extracted on or after 27 November:
  `python scripts/warranty_risk_prospective.py evaluate --freeze <freeze json> --data <newer runtime folder>`
  A partial result (matured windows only) is allowed earlier and is reported as incomplete.
- Independent of the pest-return experiment: different model file, different output folder, read-only use of Calendar data.

## Files

Created
- `webapp/analytics.py`, `webapp/warranty_risk.py`, `webapp/models/warranty_risk_v1.json`
- `webapp/static/stages.js`, `webapp/static/shell.js`, `webapp/static/archivo.woff2`, `webapp/static/archivo-LICENSE.txt`
- `scripts/research_operational_models_20261102.py`, `scripts/research_repeat_survival_20261102.py`, `scripts/research_property_warranty_20261102.py`, `scripts/train_warranty_risk.py`, `scripts/warranty_risk_prospective.py`
- `tests/test_analytics.py`, `tests/test_warranty_risk.py`, `tests/test_warranty_risk_prospective.py`
- `planning/CP2_OPERATIONAL_MODEL_SEARCH_20261102.md`, this handover, `planning/CP2_REMAINING_TASKS_20261102.md`
- `webapp/performance_targets.json`
- `outputs/model_validation/20261102_operational_search/` (study results, screenshot), `outputs/model_validation/20261102_warranty_risk_prospective/` (frozen record)
- `outputs/website_design/20261102_redesign/` (screenshots)

Edited
- `webapp/server.py` (login, `/api/analytics`, static whitelist, `/maps` redirect, Archivo font route)
- `webapp/DESIGN.md`, `webapp/analytics.py` (targets read from file)
- `tests/test_booking.py` (clock pinned), `planning/CP2_FINAL_REPORT_DRAFT.md` (model search section)
- `webapp/static/index.html`, `maps.html`, `style.css` (rewritten), `maps.css` (rewritten), `app.js`, `tools.js`, `workspace.js`, `booking.js`, `maps.js`

Deleted
- `webapp/static/workspace.css`, `crm.css`, `refinement.css`, `guide.css`, `bi.css`, `bi.js`, `analytics.js`

## Tests and known issues

- Passing here: analytics, warranty risk (+ forward test), workspace, AI-assistant removal, spatial payload, follow-up, planning tools, and both UI `.cjs` checks.
- `tests/test_booking.py` had a test that failed once the real clock passed its 2 November fixture. Fixed by pinning `booking.options` to the fixture time inside the test; `webapp/booking.py` is unchanged. 120 tests passed in the development environment.
- `tests/test_planning_forecasts.py` and `tests/test_warranty_risk_model_contract.py` need files not in the separate checkout; run them on the full checkout.
- Three `tests/test_portal.py` tests need `google.cloud` and archived files on the user's machine; not re-run here.

## Next steps

Remaining work: see `planning/CP2_REMAINING_TASKS_20261102.md` (full test run, owner targets, Word report copy, Cloud Run deploy, warranty-risk evaluation on or after 27 November, unchanged pest-return evaluation on 30 November).

The report draft `planning/CP2_FINAL_REPORT_DRAFT.md` now has the model search section and a paragraph on the redesigned website.

## 6. Second overhaul of the portal (2 November, afternoon)

The first redesign still looked generated, so the look and the content were rebuilt again. Details in `webapp/DESIGN.md` ("Overhaul: 2 November 2026"); screenshots in `outputs/website_design/20261102_overhaul/`.

- Quiet working-tool look: white pages, light sidebar, Instrument Sans, blue only for links, the main button and chart data. No top bar; sign out sits in the sidebar foot.
- New landing page **Today** (`#today`; `#decisions` redirects): four figures, then payment reminders due, properties to check in with (warranty risk) and customers to offer a maintenance package, plus next week's hours and three plain-language suggestions. Scores, weight sliders, option cards and the long action plan were removed.
- Performance and Warranty risk rewritten as a measures table, two charts, a collection bar and a collapsed model explanation.
- Plain-language wording for options and measures in `webapp/analytics.py`; middle dots and arrow glyphs removed from interface strings.
- Files: `webapp/static/{index.html,maps.html,style.css,maps.css,stages.js,shell.js,app.js,tools.js,workspace.js,booking.js,maps.js,guide.js}`, `webapp/analytics.py`, `webapp/performance_targets.json`, `webapp/DESIGN.md`, `tests/booking_calendar_ui.cjs`, `tests/workspace_ui.cjs` (labels updated).
- The `/reports` link (added to `index.html` at 05:14) is kept in the Sales dashboard view. `server.py` and `reports.html` were not touched.
- Checks: 120 Python tests and both UI `.cjs` checks pass; no console errors on any page at 1440px; Today checked at phone width.

## 7. Design merged with the feature review (2 November, evening)

- Kept the reviewed menu and content decisions from `CP2_WEBSITE_FEATURE_REVIEW_20261102.md` (Today without experimental contact lists or upsells; Research collapsed; unconfirmed targets not scored) and applied the black, white and light blue design on top: black header bands with stat tiles, white rounded cards, light blue for data and the active menu item.
- Removed the leftover assistant-style interface: "What needs checking?" / "Explain payment follow-ups" on Follow-ups, and the "Discuss it with the team" brief and "Explain the next decision" panel on the booking calendar. Backend endpoints and their tests were not changed.
- Fixed page titles for routes no longer in the menu (Payments, Performance, Areas, Accuracy by district) and the Research group now opens itself when one of its pages is active.
- Files: `webapp/static/{style.css,stages.js,shell.js,workspace.js,tools.js,index.html,maps.css}`, `webapp/DESIGN.md`. Screenshots in `outputs/website_design/20261102_overhaul/`. 120 Python tests in the separate checkout and both UI `.cjs` checks pass. Not deployed.

## 4 November: return-visit risk system (Claude)

- Decision flow: Today and the dashboard describe what happened; the return-visit risk score predicts which recent services are likely to come back; the weekly check-in plan chooses who to call for the calls staff can make; staff record each call's result, which feeds the pilot evaluation.
- Code: `webapp/return_risk.py`, `/api/return-risk`, `/api/return-risk/outcome`, Return-visit risk page in `webapp/static/stages.js`, `scripts/publish_return_risk_predictors.py`, gated hook in `scripts/cp2_reporting_release.py` (`CP2_RETURN_RISK_PREDICTORS=yes`). Tests: `tests/test_return_risk.py`.
- Report: `docs/Final Report CP2 Thevesh Chandran 24017717 Updated 20261104.docx` (new section 4.28, Table 4.8, Figure 4.6). Logbook: `docs/Logbook CP2 Thevesh Chandran 24017717 Weeks 1-6 Updated 20261104.docx`.
- Open items: Task H in `planning/CODEX_TASKS_20261102.md` (daily predictor export, deploy, pilot).

