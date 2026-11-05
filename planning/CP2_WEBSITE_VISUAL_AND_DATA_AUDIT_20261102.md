# Website visual and data audit — 2 November 2026

Reviewed the local sign-in, Today, Follow-ups, Booking calendar, Customer history, Payments, model evidence, warranty-risk research, Performance, Areas, district evaluation, dashboard shell and heatmaps at desktop width. The external Looker report remained loading during the check and is not verified.

Fixed clipped KPI headings, shared context navigation, hidden source timestamps, content bounds, UTC-to-Malaysia extraction dates, balance wording and sign-in recovery. Stale workload estimates no longer appear as current forecasts on Today. Owner targets need explicit confirmation before scoring. Maps use an unknown-area label instead of raw coordinates when no reliable name exists.

Use http://127.0.0.1:8092/#today for the verified preview. Start it with scripts/start_portal_preview.ps1. It reads approved cloud snapshots using existing local Google authentication and retains the last good release on failure.

## Evidence

- 761 Python tests passed, with 20 existing rasterio warnings. Both calendar and follow-up DOM checks passed; edited JavaScript syntax passed.
- Eight authenticated API checks passed. Results are in outputs/project_audit/20261102_visual_data_review/api_checks.json.
- Booking extraction: 2 November, 06:01 MYT; 328 events; status ready. A browser check for 3 November returned Replacement backup slots after ACE had no fitting option. No appointment was booked or moved.
- Sales and payment reporting remain on the release extracted 28 October. They are stale, not fabricated current figures.
- Failed reporting run 20261101220023c8bb88 has two programme-invariant failures. Expected CONTRACT_0002 stage 13 on 25 October no longer matches Calendar facts, also causing the commercial programme paid-stage count to fail. Preserve validation pending source review. Diagnostic queries were capped at 100 MiB each.
- Edited presentation values come from authenticated APIs. Historical model results and owner-defined team rules are fixed evidence/configuration, not live measurements. Frozen models, protocols and prediction ledgers were unchanged.

## Remaining

1. Resolve the THAS stage-13 Calendar mismatch, then rerun reporting validation, reconciliation and KPI examples.
2. Deploy local changes and verify hosted pages.
3. Complete Oracle account/capacity and actual Metabase hosting, HTTPS, persistence, data connection and MCP acceptance.
4. Finish future-model evaluation when windows mature and coverage gates pass. The location-risk candidate still needs matching/timing corrections and a valid future protocol.
5. Review unresolved location precision and mapping coverage.
6. Verify external dashboard rendering, current hosting costs and permissions.
7. Complete privacy/dependency review before backing up remaining local source; GitHub sync was partial.

Local checks do not prove every source fact or cloud component is correct. No deployment was performed in this review.
