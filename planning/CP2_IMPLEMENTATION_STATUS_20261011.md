# CP2 decision-support implementation — 11 October 2026

This checkpoint supersedes older status and test-date paragraphs, while preserving their historical records. The model remains experimental. No model weights, calibration, thresholds, target or frozen bundle were changed.

## Dashboard wording

Use **Recorded warranty visits** for the Calendar outcome, rather than “callback”. The model asks: **Will this paid service be followed by a recorded warranty visit within 30 days?** Calendar warranty/claim/callback titles and reviewed extra-session signals such as `4/3` identify this outcome. Recording a visit does not approve contractual eligibility. Ordinary paid sessions, cancelled appointments and unrelated follow-ups are not automatically positives.

A **warranty case** on model-evaluation pages means a service window followed by at least one such visit. It is not a unique customer or unique visit: one visit can fall within several preceding service windows. Warranty eligibility follows the separate owner-confirmed policy.

## Implemented and checked

- Four privacy-checked aggregate Gold views are published: `dashboard_model_review`, `dashboard_feature_comparison`, `dashboard_followup_baselines`, and `dashboard_attention`. All 11 selected dbt checks pass. The publication receipt is `outputs/project_value_review/20261011T044402/publish_receipt.json`.
- The attention view reconciles reminders, bookings and recorded balances to approved parent views. It follows those stable views after daily reporting releases. It separates grains, source freshness and meanings; no overdue/payment-sent or treatment-completion inference is made.
- Native Looker page 9 presents the small held-out test, workload, missed cases and limitations. Page 12 adds a category-filtered action list. Page 13 compares environmental inputs and a simple previous-property-warranty rule. Native viewer checks confirm four reminder rows representing five scheduled reminder entries on 13, 14, 16 and 17 October.
- The already-inspected 2025 development comparison finds 90 positive windows for the model versus 43 for the simple rule, at 397 reviews each over 1,978 services and 183 positives. Random selection would find approximately 36.69 on average. These are exploratory development results, not a new independent accuracy result.
- Environmental ablations report both ranking quality and capture. Added environmental inputs did not consistently improve both; flood additions did not qualify. No causal weather claim is made.
- A separate daily-budget comparison was declared before its 12–30 October cohort. Its protocol and code hashes are fixed in `config/cp2_followup_policy_v1.json`; the protocol is also stored immutably in the existing restricted cloud bucket. It uses the same frozen model and original timely receipts; it requires the original complete evaluation first. The original 10–30 October protocol remains unchanged.
- Cloud revision `cp2-prospective-collector-00027-few`, image digest `sha256:f50f9e9a46fe71512fc82737fc5d453bf9535a0a455ecc298256bb1198510986`, adds the supplementary evaluation after the original one. Matching original results and private outcome labels are committed together before the public-safe result copy; interruption recovery reuses that evidence instead of recalculating the original result. The supplementary output is separate and immutable.
- The new revision passed startup checks and an authenticated `/tick` (HTTP 200). Reporting and collection schedules remain enabled. The existing 30 November, 14:00 Malaysia evaluation schedule invokes the updated service; no laptop runner is needed.
- The final Python suite passes **513 tests**, with 19 existing Rasterio deprecation warnings. Frozen-model replay passed earlier in this implementation with numerical differences below `4e-16`.

## Still pending — do not claim complete

- The October audit showed zero missed **eligible** windows and one missed **candidate** window. The owner has now resolved that candidate's source ambiguity: THAS's 24-service programme combines 4 + 20 services; the earlier 3-service sale is separate. Operational reporting is corrected, while the original frozen-model audit and scope exclusions remain preserved. Zero confirmed misses is not proof of complete coverage. See [programme repair](CP2_THAS_PROGRAMME_REPAIR_20261011.md).
- Full outcomes and the one-time model evaluation cannot be completed before 30 November. Complete Calendar coverage, stable eligibility, timely receipts and all integrity checks must pass; the date does not guarantee a successful evaluation or better accuracy.
- The six-task usability protocol and blank recording template are ready. No stakeholder has completed the measured tasks, so success rate and time saved remain unmeasured.
- The full original 11-page dashboard still needs its remaining page builds and final filter, narrow-screen, privacy and viewer-access acceptance. The three updated/new decision pages do not establish completion of the entire report. Sharing was not changed.

## Verified cloud and dashboard update

- Five real Cloud Scheduler requests to collector revision `00027-few` returned HTTP 200 on 11 October; the protocol/code hash check passed. Receipt: `outputs/project_value_review/20261011/scheduled_verification.json`.
- Reporting build `750dbb88-6f5a-4cdc-b490-9330f009ca43` passed its container startup smoke check. Existing daily job `cp2-reporting-daily` now uses digest `sha256:d265fd9f54ca0fc4e3015b5c1e5940cff89791e3b3f352ffc9c2859d80d5a0c9`. Execution `cp2-reporting-daily-hjcmh` succeeded; release `20261011103927f93a7b` passed validation and published at 10:47 UTC. Its expanded reporting allowlist is hosted. One task, 20-minute timeout and zero automatic retries remain configured.
- Native Enquiries page now has the monthly chart, three reconciled cards, source-meaning notes and a month selector. September's viewer totals (540 open, 161 closed, 34 marked won) exactly match a bounded query of the published Gold source. The filter was reset to all months. Whole-source totals are 10,152 open, 6,337 closed and 279 marked won. These are records/status annotations, not unique customers or payment receipts.
- Dashboard completion, stakeholder usability and future model outcomes remain pending as described above; this release does not establish improved model accuracy.

## Native dashboard continuation

- Pests and packages: replaced the incomplete PAYMENTS-based package card with recorded Sales (RM). Corrected Package mix from pest grouping/payment-evidence count to package grouping/all package sales. Added interpretation notes and enlarged the three summary values. Published-source query confirms 861 packages, RM576,670.66 and 370 linked recorded warranty visits. Raw pest/package labels remain separate; this is not a rejected-offer or causal package recommendation model.
- Service areas: applied the page 7 design frame, replaced the unrelated recurrence table with approved aggregate area data, and separated the spatial interpretation note and radius table. Radius table now uses plain labels and ascending 1/2/5 km order, with 4/10/3 groups respectively. Cross-filtering is disabled for that sensitivity table. Map, location-coverage card, main table sorting/typography and final viewer checks remain unfinished.
- Chrome disconnected during continuation. A new tab recovered the saved edits, but subsequent native controls failed; after runtime reinitialization the extension reported “Debugger unattached.” No further edits or final screenshot verification were possible at this checkpoint. Do not describe the spatial page or whole dashboard as complete.

## Reproduce and inspect

- `scripts/build_cp2_decision_support.py`: regenerate aggregate comparison seeds from pinned historical evidence; never fits a model.
- `scripts/publish_cp2_decision_support.py`: stage, privacy-check, reconcile, then publish reversible Gold wrappers; BigQuery queries bounded to 100 MiB.
- `scripts/evaluate_cp2_followup_policy.py`: one-time supplementary comparison; rejects premature or altered evidence and repeat evaluation.
- `planning/CP2_DASHBOARD_USABILITY_TEST.md` and `templates/cp2_dashboard_usability.csv`: actual management tasks and anonymous result recording.
- `outputs/dashboard_design/20261011_decisions/`: decorative frames and live report screenshots.

## Saved stopping point — 11 October, evening

User requested finishing the current page and continuing tomorrow. Work stopped after Data checks; no new overnight desktop task was created.

- Service areas (page 7): native Google map uses approved area centroids; 2,699 shown visits, excluded low-volume/missing-location records explained. Radius group counts 1/2/5 km = 4/10/3 verified in BigQuery. Map layout corrected. Radius table header still needs Fit to data in the final polish pass.
- Weather (page 8): replaced raw table with styled monthly rainfall, humidity, and complete-weather coverage charts. Year Month grouping; separate recorded warranty versus other scheduled visits; means per source month/group; Line Breaks for missing weather. No causal claim. October weather is incomplete. Final polish: coverage Y-axis 100% label is clipped; enlarge its labels area or reduce axis font. Check legend sizing and rainfall/humidity explanatory text font.
- Data checks (page 10): decorative frame, source update register, quality issue table with affected/source denominators, overlapping-count warning, 2026 linkage/location/weather coverage indicators, UTC timestamp interpretation. Added approved dashboard_data_quality connector to report; a similarly named source was already in the wider report list, so final cleanup should check duplicate connector usage before removing any unused source.
- Coverage independently verified: 3,039 scheduled visits; 3,032 linked (99.77%); 2,769 map eligible (91.12%); 2,769 complete weather (91.12%). Query: outputs/project_value_review/20261011/dashboard_coverage_check.sql. Same location/weather percentages are correct, not a duplicated calculation.
- Source age uses current_timestamp at query time, not release time; corrected header to Age (hours) and explanatory note to age when queried.
- Data quality shows source exceptions honestly (e.g. missing totals/inferred years). They are source review items, not evidence that all data problems were fixed. No financial values invented.
- Screenshots: outputs/dashboard_design/20261011_decisions/service_areas_live.png, weather_live.png, data_checks_live.png.

Remaining dashboard acceptance: audit pages 1,3,4,5,6,11,12; correct table fit-to-data, sorts and date filters; verify recurring payment semantics; update remaining old /11 decorative frames to /13; reset Actions filter to all; check viewer permissions/private fields/narrow viewport. Full dashboard is not yet accepted. Frozen-model reliability and future evaluation remain unchanged; do not claim completed future accuracy.

Browser: Chrome 3, tab 942980255, dashboard report 590914e8-066b-4671-a130-7a62a3af435a, page p_kdmwk2uu7d in viewer mode, marked deliverable. Native AX reliable; DOM intermittent. Field metadata must be dismissed with a canvas click outside its popup (e.g. x200,y550); Escape alone may leave popup open. To size table columns: right click table > Resize columns > Fit to data. Dragging header dividers moved components instead, so avoid it. Chart component DOM order changes when bringing forward or duplicates are created. Read actual positions and text each time.
