# CP2 local refresh and future evaluation

**28 September update:** A separate fresh reporting release now feeds Gold views; see [the October submission record](CP2_OCTOBER_SUBMISSION.md). The local collector remains the prospective experiment's timing gate. Its 13:33 UTC tick reported zero logged predictions and seven missed service windows, so collection coverage is incomplete and a full-cohort future accuracy claim is not currently available. The older reporting-release note below describes the prior checkpoint.

The current v5 model answers whether a **recorded corrective Calendar callback** occurs during days 1–30 after a matched paid service. Its output is a risk probability, not warranty entitlement or proof that treatment was completed. [Current model and limits](CP2_START_HERE.md).

## Fresh local run

```powershell
.venv\Scripts\python.exe scripts\cp2_pipeline.py run
.venv\Scripts\python.exe scripts\cp2_pipeline.py status
```

The run reads nine approved Sheet tabs and all six approved Calendars using read-only APIs. It verifies positional source contracts, refreshes 30 prior days of approximately 9 km ECMWF IFS weather for the known sanitized grid cells, derives predictors and mature labels in a *temporary BigQuery session* with a 100 MiB cap per query, scores the frozen model, and checks whether any service can be prospectively logged. Fresh source records are sent as bounded BigQuery query parameters for those session-local transformations. The run does not repoint permanent Bronze/Silver/Gold tables, create permanent raw-data tables, refit the model, or publish customer scores. Missing trusted coordinates leave location and weather features null. Local source rows, scores and receipts stay under ignored `outputs/cp2-v2/live_pipeline/`.

The 28 September end-to-end run scored 205 recent service anchors. Exact sanitized-address matching reused previously trusted geocodes for 64 of the new scored anchors: missing coordinates fell from 103 to 39, and complete prior-30-day weather coverage rose from 102 to 166. This improves coverage only; an address match is an area proxy, not proof of the same property or a measured rise in prediction accuracy.

The run journal records each stage and SHA-256 of private artifacts. `last_success.json` updates only after every stage succeeds; a failed attempt is separately visible in `last_attempt.json`. A failed run can be retried with `cp2_pipeline.py resume --run-id <run_id>` while its source snapshot is still fresh. If the source is older than its availability window, start a new `run`. A valid previous result remains available after a failure. The status command checks integrity before reporting a success. Google sign-in failures require the existing read-only `renew_google_access.py` flow; rerun afterwards. No automatic warehouse-provider fallback is used.

## Recording future predictions

The frozen future cohort is **28 September–27 October 2026**. A prospective log is permitted only when the score is committed within five minutes of the Calendar service end, after the feature/source extraction, before the first local outcome day, with the same frozen bundle. No older service can be backfilled into this evidence. The runner keeps an immutable source and model receipt for each recorded anchor; an exact retry preserves the first record and conflicting evidence is rejected.

```powershell
.venv\Scripts\python.exe scripts\cp2_pipeline_tick.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_cp2_local_runner.ps1 -Mode Status
```

The lightweight tick reads Calendar service events and begins source/weather preparation shortly before a timed service ends. Feature derivation waits until the scheduled end; a second Calendar read checks that each candidate event was not cancelled or changed before its score is committed. For automatic collection during the frozen cohort, the local Windows Task Scheduler task checks every two minutes in the signed-in user's session. **This PC must be awake, connected and signed in.** Task Scheduler's last run/result and `outputs/cp2-v2/live_pipeline/last_tick.json`, `watch_events.json`, `last_attempt.json`, `last_success.json` are the operational evidence. Events are acknowledged only by exact Calendar identity after an immutable score log exists. The tick also looks back across a gap since its prior check: an expired service window is marked as missed coverage and makes the task result nonzero; it is never turned into a retrospective prediction. Source edits, late data and ambiguous matches can also leave otherwise recorded services out of the model cohort. Calendar timestamps are scheduling records, not independent completion evidence.

## Final future test

The last cohort service's inclusive 30-day window ends on **26 November**. A complete-source Calendar extraction on **27 November or later** is required before making outcome labels. The one-time local task is scheduled for **27 November 2026, 09:00 MYT**; it runs `cp2_pipeline.py final-evaluation`, which refreshes complete sources, prepares exact mature labels and evaluates the frozen logs once. Check Task Scheduler's result and the local output after it runs. If the PC was off or a transient read failed, rerun this command manually when source access returns. The source receipt must show all six Calendars, the cohort start and full completed-day outcome coverage. The evaluator requires every eligible cohort anchor to have one earlier logged prediction; it refuses missing predictions, unknown outcomes, duplicate keys and a second final evaluation. A limited or interrupted local collection therefore blocks a claim of full-cohort future accuracy; the remedy is a new predeclared future cohort after repairing collection, not a retrospective substitute.

The diagnostic from August contained only five callbacks in 100 services; its AUC improvement is uncertain. The future test is necessary to establish reliability, especially for first services.

## Business metrics have a separate release gate

[Business KPI validation](CP2_BUSINESS_KPI_VALIDATION.md) passed 12 row/monthly checks against the deployed pinned source versions, with real record examples. Fresh Sheets already differ from those September 12–13 pins. The scoring pipeline's session-local fresh sources do **not** make deployed Gold totals current. Before presenting refreshed management totals, run a governed Bronze/Silver/Gold refresh, reconcile the new pins again, and keep payment entries, scheduled services, formal claims and callbacks at their correct grains.
