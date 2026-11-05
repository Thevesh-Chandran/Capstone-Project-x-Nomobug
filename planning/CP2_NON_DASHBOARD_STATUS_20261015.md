# Non-dashboard work — 15 October 2026

Current website handover: [website acceptance](CP2_WEBSITE_ACCEPTANCE_20261015.md). Revision `cp2-portal-00017-fkv` is deployed; 563 Python tests passed. The dated checks below are retained as historical records, not the latest revision status. Report draft: [CP2 report](CP2_FINAL_REPORT_DRAFT.md). Walkthrough: [demo guide](CP2_DEMO_GUIDE.md).

Latest: [collection and assistant resolution](CP2_COLLECTION_AND_AI_RESOLUTION_20261015.md). All 23 candidates were investigated, the assistant's observed compound-question failure was repaired, and a separate 16–30 October recovery evaluation was declared before its start. The historical incomplete audit below remains preserved.

Scope: Docker, private website, Ollama, models and collection. The owner is editing Looker; no report edits are included in this checkpoint.

## Verified

- Final full Python suite: 551 passed, 19 existing rasterio deprecation warnings. Focused portal/planning tests: 22 passed; collector/pipeline tests: 27 passed. Docker Compose configuration validation passed without starting local containers.
- Frozen model replay: 5,695 rows, maximum probability differences below 2.23e-16 across all three estimators. No model weights, thresholds or collection dates changed.
- Daily reporting execution `cp2-reporting-daily-h7t9z` succeeded on 15 October at 06:08 Malaysia time. Published source extraction and the private website snapshot are dated 15 October.
- Website build `85c40fe5-bd27-46ce-a1aa-12add6907fff` succeeded, including container import smoke. Revision `cp2-portal-00014-hz5` serves 100% of traffic. Staff sign-in, connected data/Ollama and the current booking forecast were verified in Chrome.
- Forecasts require a Calendar extraction on/after Monday before treating the previous Sunday as complete. Missing or stale source freshness withholds the estimate. The UI calls scheduled counts “bookings in snapshot.”
- Website invocation remains limited to the Google IAP service agent. Ollama invocation remains limited to the portal runtime identity. No public access or new permissions were introduced.
- Local Docker Desktop's Linux engine is stopped. Container builds use Cloud Build; production does not depend on the laptop engine.

## Collector incident

The 15 October audit contains recent HTTP 500 responses at service windows. The durable last attempt failed at the sources stage with ValueError. Idle requests subsequently succeeded, which does not establish successful scoring.

The exact active collector image `sha256:f50f9e9a46fe71512fc82737fc5d453bf9535a0a455ecc298256bb1198510986` was inspected through the authenticated Artifact Registry API: its source does not support the reviewed B2B Call 1 / Call 2 column insertion. Current local extraction supports that exact layout and succeeded against all nine approved tabs and six Calendars (11,767 events). Other header changes remain subject to strict checks. This identifies a concrete deployment drift requiring repair; cloud recovery still needs a full source-to-model check.

Collector build `e94c5b1d-aa4c-48d0-b90c-d1261a9abab4` succeeded. New revision `cp2-prospective-collector-00016-gv7` (created today despite its lower sequence number) serves 100% of traffic. The service previously pinned traffic to revision 27; an image update alone did not switch it, so routing was explicitly updated and verified.

Recovery run `20261015T144312Z_c90a4fad` completed all five stages and returned HTTP 200. Durable `state/full_smoke.json` and `state/last_attempt.json` both record success. Zero prospective predictions were logged during this after-hours smoke. The subsequent genuine scheduled tick at 22:46 Malaysia time was healthy and retained all 60 raw missed candidates and the unchanged current-cohort counts. A temporary authenticated smoke trigger collided once with an active tick (409); retry succeeded, and the temporary trigger was paused and deleted. IAM, frozen artifacts, source access and the regular schedules were preserved.

At 22:30 Malaysia time the audit reported 60 raw missed candidate windows. The current October 10 cohort contains 23 missed candidates: two classified eligible and 21 unresolved. These are candidate windows, not 23 confirmed missing eligible predictions. Historical timestamps and receipts must remain unchanged. The strict complete-cohort evaluation cannot pass while known eligible misses remain; 30 November is an outcome-maturity date, not a repair for those misses.

## Model limits and remaining acceptance

Original pest-return model: historical 94% accuracy versus the same sample's 95% no-return baseline; five positive cases among 100. It remains experimental. The weekly baseline and repeat-purchase ranking are additional experimental tools, not replacements or proven accuracy improvements. The repeat study has 19 positive test customers and needs 90-day outcomes for a fresh test.

Real hosted Ollama test: the commercial 12x warranty question returned the correct “No” with warranty_policy evidence, HTTP 200, but took 83.33 seconds. This is a material latency limitation, not broad AI acceptance. Three fixed policy FAQs now have tested direct answers labelled Verified project evidence, without invoking Ollama; broader questions retain Ollama. Final deployment of that FAQ improvement is recorded separately when verified.

Final FAQ deployment verified: build `46b5490d-9f49-4bc7-9f42-46974523ac33`, revision `cp2-portal-00015-58q`, 100% traffic. Staff session survived the update. The built-in residential 3x rescheduling question returned the correct 30-day condition with Verified evidence and Warranty policy source. Server request latency was 0.00444 seconds (not a browser end-to-end latency measurement). Proof: `outputs/project_audit/20261015_non_dashboard/verified_policy_live.png`. The collector's genuine 22:50 scheduled tick remained healthy with no new misses; historical counts stayed unchanged.

Remaining: reconcile unresolved candidates without inventing source facts; broader real Ollama answer/latency checks; hosted snapshot failure/recovery check; current project spending review and final non-dashboard submission evidence. A current planning estimate is not a previously logged prospective forecast. Recovery does not establish the next genuine service-end receipt until one happens.
