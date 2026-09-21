# Scripts — choose the active path

## Active BigQuery workflow

Run from the repository root with `.venv` active. BigQuery is the primary warehouse; upload scripts retain explicit project, region, approval and size gates.

| Script | Purpose |
|---|---|
| `check_bigquery_connection.py` | Read-only dataset/region check |
| `extract_prospects_2026.py` | Live Sheets extraction and profiling; no upload |
| `load_prospects_2026_bigquery.py --upload` | Explicit BigQuery Bronze upload |
| `preview_prospects_2026_silver.py` | Read-only pandas preview; defaults to BigQuery |
| `inspect_prospects_2026_categories.py` | Read-only aggregate labels/counts for five business-category columns |
| `read_prospects_2026_bigquery.py` | Internal reader used by the preview; normally not run separately |
| `renew_google_access.py` | Renew source OAuth only when needed |
| `inventory_google_sources.py` | Source metadata discovery when needed |
| `load_operational_bronze.py --upload` | Live API contract check and immutable Bronze load for the eight operational Sheets tabs |
| `load_payment_date_serials.py` | Read-only date/reference lineage plan for the PAYMENTS underlying Sheets date cells; `--upload` stores an immutable, verified date-only Bronze sidecar behind the normal upload gate |
| `build_operational_silver.py --build` | dbt preflight/build for the nine operational Silver views and tests |
| `load_calendar_bronze.py --upload` | Complete paginated read of the six approved Calendars into one immutable Bronze snapshot; cancelled events retained |
| `build_calendar_silver.py` | Builds/tests the safe Calendar event view without raw descriptions or locations |
| `build_gold_foundation.py` | Builds/tests Gold fact, provisional monthly activity and quality views |
| `inspect_weather_location_readiness.py` | Read-only 2026 Calendar/Sales location-shape coverage by event category; prints aggregate counts only, no weather request |
| `inspect_calendar_address_blocks.py` | Read-only, in-memory 2026 Calendar address-block and conservative string-grouping check; default output is aggregate-only, optional `--review-continuations` or `--review-multi-string-sales` prints private source details |
| `export_missing_postcode_events.py` | Private HTML review page for 2026 service-like events whose extracted address line lacks a five-digit token; includes Calendar links and source descriptions, no source writes |
| `pilot_geoapify_calendar.py` | Plan/execute privacy-filtered Geoapify geocoding with de-duplicated private cache and request caps |
| `summarize_geoapify_calendar.py` | Aggregate-only current geocode tier and event-coverage summary |
| `load_calendar_geocodes_quality.py` | Creates the sanitized event-coordinate Quality table; refuses overwrite |
| `fetch_open_meteo_weather.py` | Resumable, cached ECMWF IFS daily weather fetch by sanitized coordinate only |
| `load_open_meteo_weather_quality.py` | Validates and creates the partitioned daily weather Quality table; refuses overwrite |
| `inspect_calendar_location_coverage.py` | Aggregate coordinate/weather coverage by event category and warranty-claim signal (explicit warranty labels or post-package sequences) |
| `inspect_spatial_cluster_sensitivity.py` | Aggregate 1/2/5 km DBSCAN sensitivity summary; radii are analytical, not biological |
| `inspect_weather_repeat_association.py` | Aggregate descriptive weather comparison for warranty-claim candidates versus normal scheduled service on complete 14-day coverage; not causal/predictive |

### Calendar matching diagnostics

The `inspect_calendar_*_candidates.sql`, `inspect_calendar_*_shapes.sql` and
`inspect_calendar_match_gaps.sql` files return only aggregate counts or field
labels. Run one from PowerShell with:

```powershell
Get-Content -Raw scripts/inspect_calendar_email_join_candidates.sql |
  bq query --use_legacy_sql=false --location=asia-southeast1
```

They are investigation aids, not source loaders; no raw customer values are
printed or written.

## Neon fallback

`neon/` contains the preserved connection, storage-check and loader scripts. Example: `python scripts/neon/check_neon_storage.py`. The existing Neon snapshot is preserved, not automatically synchronized.

For the shared preview explicitly set `$env:NOMOBUG_WAREHOUSE='neon'` in PowerShell, then run `python scripts/preview_prospects_2026_silver.py`. Set it back to `'bigquery'` when finished. Never mix provider outputs or switch automatically after quota failures.

## Retained prototypes

`prototypes/` contains the older three full-source profilers, historical CSV inspector, Calendar parser and weather prototype. They are reference implementations, not the current pipeline. Some write local data or initiate consent: do not run the entire folder indiscriminately.

## Beginner notebooks

The same profiling work is presented as short pandas cells under `notebooks/`:

- `01_prospects_2026_b2b_profile.ipynb`
- `02_sales_payments_profile.ipynb`
- `03_calendar_events_profile.ipynb`

Use the notebooks when learning or inspecting each step. Keep these Python scripts as repeatable command-line versions for later automation.

## Output policy

Raw company data and generated profiles belong only in Git-ignored `data/` locations. Credentials belong in the ignored `secrets/` directory or private `.env`. Do not upload those files to GitHub.
