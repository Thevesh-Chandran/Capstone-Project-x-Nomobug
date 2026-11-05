# the development workspace tasks from the the separate development session session, 2 November 2026

the separate development session worked on the project during the week of 2 November and handed the rest to Codex. Read `planning/CP2_PROJECT_HANDOVER_20261102.md` first. This file lists only what the development workspace still has to do, in date order.

## Status of the 2 November plan

| Step | Status |
|---|---|
| 1. Run the tests, fix the booking test tied to 2 November | Done. `tests/test_booking.py` now pins `booking.options` to the fixture time. 120 related tests passed in the development environment. the development workspace still has to run the full suite on the user's machine (task A). |
| 2. Real owner targets | Done as configuration. The targets now live in `webapp/performance_targets.json` with status `placeholder`. The owner has not confirmed any values yet (task B). |
| 3. Live warranty-risk test | Started 2 November. Frozen record in `outputs/model_validation/20261102_warranty_risk_prospective/` (task E). |
| 4. Model search in the report | Done in `planning/CP2_FINAL_REPORT_DRAFT.md`: new section "2 November operational model search and warranty-risk model" and a paragraph on the redesigned website. The Word report still has to be updated (task C). |
| 5. Deploy to Cloud Run | Not done. the separate development session cannot authenticate to the GCP project (task D). |
| 6. Leave the frozen pest-return model alone | Respected. No change to `config/cp2_model_current.json`, cohort configs, the collector, the ledger or `scripts/evaluate_matured_cp2_subset.py` (task F). |

## A. This week: full test suite

1. Run `python -m pytest -q` from the project root.
2. Known: `tests/test_planning_forecasts.py` and `tests/test_warranty_risk_model_contract.py` import `scripts/cp2_planning_job.py` and `train_warranty_risk_baseline`. These were not in the separate checkout, so the separate development session did not run them. They should pass on the full checkout. If `test_warranty_risk_model_contract` refers to an older warranty-risk baseline, check that it does not collide with the new `webapp/models/warranty_risk_v1.json`.
3. Start the portal locally (`python -m webapp.server`). Sign in with `admin` / `admin` and open every sidebar page. Check that the browser console shows no CSP errors.

## B. When the owner replies: confirm the targets

The Performance page reads `webapp/performance_targets.json`. For each target the owner approves:

1. Set `target` and `watch` to the owner's values.
2. Set `status` to `confirmed`, `confirmed_by` to the owner's name and `confirmed_on` to the date (YYYY-MM-DD).
3. Run `python -m pytest -q tests/test_analytics.py`.

The page label changes from "target to confirm with the owner" to "owner target, confirmed <date>". Until then the report must call these figures working targets, not owner targets.

## C. Report: Word copy

1. Copy the new draft section and the website paragraph into a new copy of `docs/Final Report CP2 Thevesh Chandran 24017717 Updated 20261028.docx`. Keep the original file.
2. Follow `planning/WRITING_VOICE_GUIDE.md`. Do not use em dashes.
3. Once the 30 November results exist, add them as described in task E and task F.

## D. Deploy the portal (once task A passes)

1. Build: `gcloud builds submit --config cloudbuild.portal-web.yaml .`. The build runs the existing smoke step.
2. Update the existing `cp2-portal` service in `asia-southeast1` to the new image. Use the usual update method so the current environment stays as it is, especially `CP2_AUTH_MODE=iap` and `CP2_IAP_AUDIENCE`. Do not add a staff-code secret.
3. `Dockerfile.web` copies `webapp/`, so `performance_targets.json`, `models/warranty_risk_v1.json`, `archivo.woff2` and the new static files go into the image. Check that `/api/analytics` and the Warranty risk page work on the live service.
4. With IAP, the username/password screen should not appear. The sign-out button reads "Switch Google account".
5. The collector, reporting job and Scheduler entries are separate services and are not touched by this deploy. Record the new revision name in `planning/CP2_WEBSITE_ACCESS.md`.

## E. 27 November or later: warranty-risk forward test

- Frozen record: `outputs/model_validation/20261102_warranty_risk_prospective/freeze_20261102T033350Z.json`, with its `.sha256`. It holds 149 windows from the 28 October snapshot, 9.22 expected warranty visits and 14 high-risk windows. The last window ends 27 November.
- Write-once. Never edit, re-freeze or overwrite it. Before evaluating, check the hash: `sha256sum freeze_20261102T033350Z.json` must match the `.sha256` file.

Steps:

1. Wait for the daily reporting job to publish a runtime snapshot extracted on or after 27 November. Use a snapshot from the 28th or later so that visits on the 27th are recorded.
2. Run:
   `python scripts/warranty_risk_prospective.py evaluate --freeze outputs\model_validation\20261102_warranty_risk_prospective\freeze_20261102T033350Z.json --data <runtime folder containing business_tools_private.json>`
3. Save the printed JSON as `outputs/model_validation/20261102_warranty_risk_prospective/evaluation_<date>.json`, next to the freeze.
4. Report:
   - matured and pending windows, and whether the run is `complete`;
   - warranty visits recorded against the 9.22 expected;
   - the high-risk hit rate against the other windows;
   - capture in the top 20%;
   - AUC and AP, only if there is at least one positive and one negative.
5. With about 9 expected positives the sample is small. Present the result as an early check, not proof of performance. If `complete` is false, say so.
6. Keep this result separate from the pest-return evaluation. It is a different model, a different label and a different population.

An earlier run before 27 November is allowed only as a partial check. It must be labelled incomplete.

## F. 30 November: pest-return evaluation (unchanged)

Use the development workspace's existing process, `planning/CP2_NOVEMBER30_FINISH.md` and `planning/CP2_COLLECTION_AND_AI_RESOLUTION_20261015.md`. It was unchanged in that revision:

- October 10 cohort at 14:00 and recovery cohort at 15:00, Malaysia time.
- Report the 24 missed windows and the unresolved candidates as recorded on 1 November.
- If a completeness or integrity gate fails, report the rejection rather than an accuracy figure.

## G. After both evaluations

1. Update `planning/CP2_FINAL_REPORT_DRAFT.md`, the Word copy and `planning/CP2_COMPLETION_STATUS.md` with both results.
2. Pause or archive the 2026 experiment Scheduler entries, as noted in `CP2_NOVEMBER30_FINISH.md`.
