> **Resolved — 21 October 2026:** Google now shows **In production**. The same read-only connection was renewed afterward, Secret Manager token version 5 installed, refresh exchange and both approved Sheets metadata checks passed, and cloud source/model check `cp2-planning-weekly-gvqkf` succeeded. Earlier Testing/pending notes below describe the previous state. Evidence: `outputs/oauth_publication/20261021/production_verified.json`. Model weights and workspace permissions were unchanged.

# Planning forecasts — 21 October 2026

The website's **Planning & models** page now leads with two research candidates:

| Question | Selected method | Historical average error | Strong simple baseline |
|---|---|---:|---:|
| Calendar booking entries over the next two weeks | Extra Trees, 36 inputs | 12.76 entries | 20.73 entries |
| Booked appointment hours over the next week | Ridge, 32 inputs | 8.97 hours | 11.77 hours |

These are forecasts of recorded Calendar entries and appointment durations. They are not completed treatments, unique customer visits, productivity or available staffing capacity. The page shows separate actual/forecast/baseline charts and keeps old research collapsed. The original pest-return model stays experimental and unchanged.

## Automatic run

- Cloud Run Job: `cp2-planning-weekly`, `asia-southeast1`.
- Cloud Scheduler: `cp2-planning-weekly-trigger`, Sunday **23:50 Malaysia time**.
- First forecast window: **Monday 26 October 2026, 00:00 MYT**. One output covers seven days; the other covers fourteen days, with exclusive window ends.
- One task, one CPU, 2 GiB, 20-minute timeout, **zero automatic retries**.
- Dedicated identity: `cp2-planning-job`. It reads the existing approved read-only Google credentials and Calendar inventory from restricted Secret Manager. It cannot write Sheets or Calendar.
- Private audit bucket: `gs://cp2-planning-private-profound-keel-500007-s4/v1/`. Uniform access and public-access prevention are enabled. It retains source snapshots, weather, per-week fitted models, aggregate training matrices, immutable predictions and outcomes.
- The job can write only `current/planning_forecast.json` in the portal bucket. The website reads this aggregate file; it has no access grant to the new private audit bucket.
- No laptop process, Windows scheduled task or the development workspace heartbeat is involved.

The existing two-minute pest-return collector and daily reporting job remain separate. The dashboard was not edited.

## What is frozen

`config/cp2_planning_v1.json` fixes both targets, algorithm configurations, feature formulas, training-history rules and baseline choices. Model parameters are refitted weekly on earlier timestamp-matured windows, as declared. Each fitted model is saved and hashed.

The cloud's immutable `implementation.json` also binds the engine code, job code and dependency versions. A later code/dependency change must use an explicitly declared new runtime prefix rather than silently altering this experiment.

Inputs include partial advance bookings, recent booking counts and booked hours, rolling averages/changes and calendar context. The booking-count candidate also uses older regional rainfall, temperature and humidity. Weather requests use only the fixed Kuala Lumpur regional coordinate, never customer addresses. The latest weather observation precedes the forecast origin by at least seven days.

## Honest forward evaluation

1. A primary receipt is allowed only in the final 30 minutes before Monday. Source capture, model artifacts and the forecast must all be committed before the week starts. GCS server creation time is checked, not just a client timestamp.
2. Prediction records are create-only. A late/missing week is preserved as a miss, with its original deadline. Neither viewing the website nor rerunning a job can backfill it.
3. Each horizon is evaluated separately after its window ends and at least three days of revision buffer. The weekly job's next run may add several more days of buffer.
4. Each outcome is recorded once and bound to its prediction/protocol hash. Changed model/source/protocol evidence is rejected. Mean absolute error and WAPE are shown separately from the historical results; WAPE is not accuracy.
5. An early manual source check deliberately creates **no primary forecast**. The initial website therefore correctly shows zero logged/evaluated weeks and the first expected week, rather than invented current predictions.

The live job starts ten minutes before Monday. Its training pool excludes any outcome window still open when source capture began. Historical research fitted at Monday origins and used reconstructed surviving records. This timing difference and incomplete past Calendar versions mean historical error is not a live-performance guarantee.

## Failure and retry

A failed refresh leaves the last successful portal forecast intact. Its own timestamp and cycle dates expose staleness. Gold reporting views are unaffected. Inspect the job failure before retrying; do not rerun a missed primary window as if it were timely.

Safe manual access/model check:

```powershell
gcloud run jobs execute cp2-planning-weekly --project profound-keel-500007-s4 --region asia-southeast1 '--args=-m,scripts.cp2_planning_job,--check' --wait
```

The quoted comma-separated `--args` value matters in PowerShell. An unquoted override was recorded as a failed execution; the job's persisted default command remained correct.

If Google access expires, run `scripts/renew_google_access.py --timeout 900`, finish the same read-only consent, validate the scope list and update the existing `cp2-google-readonly-token` secret. Never print credentials or put them in the image/logs. Then rerun the manual check and inspect the Scheduler-dispatched execution. A longer sign-in window is supported; cancellation still preserves the previous token.

## Verification

- **658 Python tests passed**, including exact selected-model replay, future-added-event isolation, server commit-time timeliness, cancelled-versus-Sunday classification, separate outcome maturity, one-time evaluation, missing-window preservation and altered-model rejection.
- Both final container builds and smoke imports passed.
- Manual cloud source/model check succeeded: `cp2-planning-weekly-qqsw5`.
- A real Cloud Scheduler dispatch succeeded: `cp2-planning-weekly-gqn5q`. This checks the dispatch/IAM path; the first natural Sunday clock run is still in the future.
- Initial live state has zero predictions and zero evaluated outcomes, as expected before 26 October.
- Browser checks verify the two charts and experimental labels. A direct Windows HTTP probe returned a gateway 404; authenticated browser checks and the local API suite are used instead, without weakening authentication.
- Rollout receipts and screenshots: `outputs/planning_rollout/20261021/`.
- Original bundle SHA-256 remains `6ace4314b4a5e170ea1bd6feee40dadbdd14eb3c986db9223d888b3c3ee302e0`; the existing model pointer is unchanged.

Review the festival calendar before forecasts extend into a year without reviewed dates. Do not silently substitute an empty holiday calendar. Source access can still expire; an enabled schedule alone is not proof that a particular future collection succeeded.

## Source-access durability check — 21 October 2026

The Google Auth Platform Audience page was inspected read-only after successful cloud checks. Publishing status is **Testing**, user type **External**. The console requires completing Branding before publishing. Google documents a seven-day refresh-token lifetime for external Testing apps using these scopes: https://developers.google.com/identity/protocols/oauth2/ . Current access works, but unattended collection beyond that token lifetime is not yet assured. The owner has been asked to complete the publishing configuration; renew and verify the same read-only access afterward. No OAuth publishing, scope or access changes were made by this audit.

The published normal website was checked in an authenticated browser at desktop size: both forecast charts, historical baseline comparisons, pending first week, and original experimental model labels are present. Browser console errors: none. The existing core reporting snapshot still displays its own freshness warning; this rollout does not claim to have refreshed that separate reporting pipeline.
