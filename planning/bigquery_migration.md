# BigQuery primary; Neon retained

Run commands from the repository root.

## Decision and status

4 September 2026: the user's Billing Overview explicitly confirmed Paid account, upgraded on 3 September. The user accepts residual billing risk and authorizes continuing the BigQuery migration while targeting RM0. Promotional credit does not establish protected Free Trial status. Budget, query quota, credit expiry, region and ADC checks remain pending; acceptance of risk does not authorize unrelated paid services or automatic upgrades. Neon remains untouched.

User authorized conversion to BigQuery on 3 September 2026 and keeping Neon in case limits are reached. This is not authorization to silently incur charges. BigQuery billing-linked free allowances are not a guaranteed $0 cap. No billing settings have been changed and no BigQuery customer-data load has been run by the agent.

Verified Neon fallback: one Prospects 2026 snapshot, 32,580 rows, exact values/positions checked and identical rerun skipped. Neon storage was 18.82 MiB database-wide. This is a fallback checkpoint, NOT a continuously synchronized backup. Its 0.5 GB allowance is still a constraint.

## Before BigQuery upload

1. Confirm project ID and one dataset region appropriate for approved company-data storage. Do not assume an existing region or recreate datasets.
2. Confirm BigQuery API and company-data access approval. Paid billing status is verified from the user's screenshot. Configure conservative project-wide on-demand query quota (revised initial target 2 GiB/day = 0.001953125 TiB/day; verify accepted UI precision), an RM10 monthly alert budget, and no capacity reservations. Exclude promotional credits from the alert calculation so they do not hide usage costs; keep Free Tier savings included. Check credit expiry separately. Other billing-account usage shares allowances. Daily quotas are approximate and budgets do not stop spending. None of these settings has yet been verified as applied.
3. Establish Application Default Credentials separately from the read-only Sheets/Calendar token. Prefer user ADC for local development; no service-account key download is required. If no ADC exists, install Google Cloud CLI and use `gcloud auth application-default login`. This replaces existing local ADC if present, so inspect the existing setup first. Never share callback URLs/tokens.
4. Add `NOMOBUG_BQ_PROJECT` and `NOMOBUG_BQ_LOCATION` to private `.env`. Keep `DATABASE_URL` and all existing source settings unchanged.
5. Run `python scripts/check_bigquery_connection.py`. This reads metadata only and does not prove DML/billing/write access.
6. Create missing datasets deliberately in the confirmed region: bronze, silver, gold, quality, audit, analytics_ml. Review existing expiry settings; do not expose Bronze to reporting/public roles.
7. Only after review set `NOMOBUG_BQ_UPLOAD_APPROVED=yes`; then run `python scripts/load_prospects_2026_bigquery.py --upload` and repeat once to verify unchanged-snapshot skip.

The approval flag is a local acknowledgement, NOT a verification of cloud budget settings. Future dbt/dashboard queries must include byte limits where supported and project quotas must cover all clients. No query jobs are used by this first loader/checker.

## Raw storage design

One atomic batch load per unique source snapshot into `bronze.prospects_2026_<sha256>`. The same fingerprint structure is used by the Neon loader. Source columns are STRING with original header text in field descriptions; row positions are explicit. Snapshot timestamps/counts are in the table description. Duplicate and template rows are preserved. Existing snapshots are verified, never appended or overwritten. Failed post-load verification blocks success but does not delete a committed table.

For this initial manual phase the loader refuses a sixth distinct snapshot or a new source payload above 100 MiB. These are conservative workflow gates, NOT account-wide storage limits: other datasets, users, concurrent runs and billed representations can differ. Run one loader at a time; review actual storage before scheduling. Do not expose a wildcard union of historical snapshots to dashboards, which would multiply counts.

## Manual fallback procedure

On a BigQuery quota/cost alert: stop new scheduled work, record the last successful snapshot, investigate the actual limit. Do NOT automatically retry on Neon or enable paid capacity. Check Neon space/compute and obtain a manual switch decision. Use its retained loader/preview, compare source snapshot hashes and row counts, and identify the active provider and freshness in reporting. Never combine both providers' facts or merge snapshots as new customers.

Neon fallback scripts are now under `scripts/neon/`: `check_neon_connection.py`, `check_neon_storage.py`, `load_prospects_2026_bronze.py`. The shared Silver preview remains under `scripts/` and defaults to BigQuery after conversion; select `NOMOBUG_WAREHOUSE=neon` explicitly for fallback. PostgreSQL/dbt SQL requires separate validation, not just swapping a connection string.

## Remaining acceptance gates

- Live BigQuery connection, dataset region and cost-control review.
- First cloud load and rerun comparison against the retained Neon snapshot (source may have changed; compare hashes before expecting equality).
- BigQuery Silver preview, dbt debug/model tests and restricted dashboard connection.
- Storage retention, query-budget and fallback rehearsal before scheduling.
- No proposal or CP1 document changes; no Git push requested.

References: [Google ADC](https://docs.cloud.google.com/docs/authentication/application-default-credentials), [BigQuery batch loads](https://docs.cloud.google.com/bigquery/docs/loading-data-cloud-storage-json), [custom quotas](https://docs.cloud.google.com/bigquery/docs/custom-quotas), [query cost controls](https://docs.cloud.google.com/bigquery/docs/best-practices-costs).
