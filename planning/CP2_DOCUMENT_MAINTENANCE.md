# CP2 document maintenance

Last verified work cutoff: 1 November 2026, Malaysia time. Prepared on 2 November at the user's request to include work only through yesterday.

## Current Word deliverables

- docs/Final Report CP2 Thevesh Chandran 24017717 Updated 20261101.docx — 80 pages, including 55 main-body pages.
- docs/Logbook CP2 Thevesh Chandran 24017717 Weeks 1-5 Updated 20261101.docx — 11 pages. Weeks 1-4 preserved; Week 5 covers 27 October to 2 November but records work only through 1 November.

Prior dated outputs and the historical CP1 proposal are preserved. In this chat, the user's reference to updating the proposal was interpreted as maintaining the CP2 final report, which is the ongoing deliverable.

## Weekly maintenance

The active the development workspace heartbeat is weekly-cp2-report-and-logbook-update, attached to CP2 REPORT AND LOGBOOK. It runs Sundays at 21:00 Malaysia time. Update only work actually completed through the chosen Sunday cutoff. Semester Week 1 starts 29 September; seven-day weeks therefore run Tuesday to Monday. Sunday updates may end partway through the numbered academic week. Extend that entry at the next run rather than duplicating it.

Use the latest verified dated Word files as the starting point. Do not rerun older hardcoded report builders or diagram replacement scripts against the latest file: some recreate a 28 October snapshot and would discard later edits. Make a new dated version and preserve earlier deliverables. Use planning/WRITING_VOICE_GUIDE.md, CP1 formatting and supervisor Dr Nauman Ali Khan. Keep the original Python research graph files byte-for-byte; the user objected only to the explanatory diagrams, not to those graphs.

## Evidence included in this update

- 28 October reporting recovery, collector timing controls, incomplete coverage and failed calibration promotion: planning/CP2_MAIN_MODEL_REVIEW_20261028.md and dated aggregate receipts.
- Booking extension as recorded on 30 October in planning/CP2_WORKSPACE_PURPOSE.md and outputs/website_design/20261030_decision_workspace. Keep the independent booking-feed date separate from the stale financial release.
- 1 November partial matured-subset assessment and recovery audit: planning/CP2_PARTIAL_EVALUATION_20261101.md and outputs/project_audit/20261101_outcome_repair/partial_evaluation.json. Fourteen scored timely receipts, one return, TP/FP/FN/TN 0/0/1/13, 92.9% accuracy equal to the no-return baseline, precision undefined and recall zero. Recovery audit: 24 missed eligible predictions and 16 unresolved candidates. This is not a complete-cohort result.
- 1 November assistant removal: planning/CP2_AI_ASSISTANT_REMOVAL_20261101.md and its acceptance.json. Current scope excludes generative chat and the retired Ollama service; historical tests remain documented. The removal record contains 744 passing Python tests and two final removal checks.

Work from 2 November, including new operational-model research, property-risk models, portal redesign, dashboard work and any later releases, is outside this cutoff. Review dated completion evidence before including it in the next weekly revision. A note modified later is not by itself evidence that all of its contents occurred before the cutoff.

## Verification

See .codex-tmp/report_update_20261101/final_validation.json and visual_review.json for internal QA. All original media and non-document package parts are preserved; all 129 contents targets were checked against the final Word export. No final model evaluator, live cloud extraction, deployment or source-data change was performed for document maintenance. Maintain this record after each successful weekly update.
