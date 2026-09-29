# CP2 local refresh and future evaluation

**29 September owner decision (about 22:00 MYT):** The owner declined an always-awake laptop requirement. `Nomobug CP2 Prospective Local` was disabled and verified `Disabled`; no hosted collector is deployed. The repaired-cohort protocol remains unchanged, but collection is paused. Its full-cohort November evaluation must not run or claim accuracy unless complete, timely predictions actually exist for every eligible service. The existing cloud BigQuery reporting job continues independently. The October submission instead uses the historical held-out result, with its stated uncertainty. The operational description below documents the paused collector and should not be read as a currently active schedule.

**29 September update:** A separate daily cloud reporting release now feeds Gold views; see [the October submission record](CP2_OCTOBER_SUBMISSION.md). The local collector remains the prospective experiment's timing gate. Its evening catch-up found 20 missed service windows and zero logged predictions, so the original full-cohort future accuracy test is invalid. The task now runs on battery with windowless Python, and an automatic scheduled tick has succeeded. A separately [predeclared repaired cohort](../config/cp2_repaired_cohort.json) covers 30 September–27 October using the unchanged model. The older reporting-release note below describes the prior checkpoint.

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

The original frozen future cohort is **28 September–27 October 2026**. Its missed windows remain immutable audit evidence. A separate repaired evaluation cohort was declared before its first day: **30 September–27 October 2026**, with the same frozen model, target, eligibility and five-minute logging gate. Its protocol binds the exact model-bundle hash and declaration timestamp; it does not refit or alter the model. A prospective log is permitted only when the score is committed within five minutes of the Calendar service end, after feature/source extraction and before the first local outcome day. No older service can be backfilled into either cohort. The runner keeps an immutable source and model receipt for each recorded anchor; an exact retry preserves the first record and conflicting evidence is rejected.

```powershell
.venv\Scripts\python.exe scripts\cp2_pipeline_tick.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_cp2_local_runner.ps1 -Mode Status
```

The lightweight tick reads Calendar service events and begins source/weather preparation shortly before a timed service ends. Feature derivation waits until the scheduled end; a second Calendar read checks that each candidate event was not cancelled or changed before its score is committed. The local Windows Task Scheduler task checks every two minutes in the signed-in user's session. It uses `pythonw.exe` so no terminal appears and is allowed to start and continue on battery. **This PC must still be awake, connected and signed in.** The task does not wake the PC from sleep, and the active AC/DC power plan disables wake timers. Run `scripts/install_cp2_local_runner.ps1 -Mode Status` to check the scheduled result and battery setting; `-Mode Repair` restores the windowless actions, battery settings and a fresh trigger through 27 October. Task Scheduler's last run/result and `outputs/cp2-v2/live_pipeline/last_tick.json`, `watch_events.json`, `last_attempt.json`, `last_success.json` are operational evidence. Events are acknowledged only by exact Calendar identity after an immutable score log exists. The tick looks back across gaps: an expired service window is marked as missed coverage and makes the task result nonzero **on the tick that discovers it**; later healthy ticks return zero while cumulative `coverage_status` remains `incomplete`. Missed windows never become retrospective predictions. Source edits, late data and ambiguous matches can also leave otherwise recorded services out of the model cohort. Calendar timestamps are scheduling records, not independent completion evidence.

## Final future test

The repaired cohort's last service date remains 27 October, so its inclusive 30-day outcome window ends on **26 November**. A complete-source Calendar extraction on **27 November or later** would be required before making outcome labels. The one-time local evaluation task was not found in Task Scheduler during the 29 September pause check. Do not install or run it as a substitute for missing prediction coverage. If a valid hosted collection path later exists, the source receipt must show all six Calendars, the cohort start and full completed-day outcome coverage. The evaluator requires every eligible repaired-cohort anchor to have one earlier logged prediction; it rejects missing or late predictions, unknown outcomes, duplicate keys, changed protocol/model hashes and a second evaluation. The original incomplete cohort remains recorded and is never overwritten; no retrospective substitute is allowed.

The diagnostic from August contained only five callbacks in 100 services; its AUC improvement is uncertain. The future test is necessary to establish reliability, especially for first services.

## Business metrics have a separate release gate

[Business KPI validation](CP2_BUSINESS_KPI_VALIDATION.md) passed 12 row/monthly checks against the deployed pinned source versions, with real record examples. Fresh Sheets already differ from those September 12–13 pins. The scoring pipeline's session-local fresh sources do **not** make deployed Gold totals current. Before presenting refreshed management totals, run a governed Bronze/Silver/Gold refresh, reconcile the new pins again, and keep payment entries, scheduled services, formal claims and callbacks at their correct grains.
