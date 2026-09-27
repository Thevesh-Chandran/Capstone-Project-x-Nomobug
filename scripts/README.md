# Scripts — choose the active path

## Current model workflow

Start with [the model guide](../planning/CP2_START_HERE.md) before running an experiment. Commands use `.venv/Scripts/python.exe` from the repository root. Existing frozen results are private local artifacts; a rerun is not a new independent test.

| Script | Use |
|---|---|
| `cp2_model.py status` | Read the current corrected v5 model pointer, training coverage and evaluation limits |
| `cp2_model.py verify` | Replay the current corrected future bundle and check its hashes |
| `cp2_model.py predict --input-json <private predictors> --output-csv outputs/<private scores>.csv` | Generate risk scores without manufacturing observed outcomes; this does not register prospective evidence |
| `cp2_model.py log-prospective --input-json <private predictors>` | Log the current frozen comparison with strict timing gates; the live feature feed is not connected |
| `cp2_model.py evaluate-prospective --input-json <private Calendar labels>` | Evaluate the mature frozen cohort once, with complete coverage, no earlier than 27 November |
| `compare_callback_candidates_v2.py` | Reproduce the corrected v5 fixed candidate selection and artifact generation |
| `refresh_callback_validation.py` | Derive a separate corrected candidate input from refreshed source evidence |
| `evaluate_callback_holdout.py` | Evaluate the frozen selected models on the reserved newer-date cohort; refuses result overwrite |
| `reconcile_callback_evidence.py` and `trace_claim_service_dates.py` | Preserve source-label/date audit evidence |

Use `--help` for accepted inputs and [the corrected v5 report](../planning/CP2_CORRECTED_MODEL_CANDIDATES_V5.md) for timing, coverage and immutability requirements. The governed configs are mapped in [config/README.md](../config/README.md).

Historical `benchmark_warranty_models.py`, `compare_callback_blind_spots.py`, `freeze_callback_prospective.py` and `write_warranty_benchmark_report.py` remain for reproduction; use the current entry point above to follow the corrected v2 future bundle. The v4 report generator writes its report into `planning/archive/model_evaluations/` and does not replace the current v5 pointer. [Archived reports](../planning/archive/README.md) explain the older experiments.

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


## Current corrected v5 model

Use `python scripts/cp2_model.py status` or `verify` first. `predict --input-json <predictors> --output-csv outputs/<scores>.csv` generates private risk scores; `log-prospective` and `evaluate-prospective` retain controlled future-test requirements.

Reproduction stages are `load_calendar_bronze.py --private-snapshot-json outputs/<new-source>.json` (read-only), `refresh_callback_validation.py`, `compare_callback_candidates_v2.py`, `evaluate_callback_holdout.py` (one final result), and `freeze_corrected_callback.py` (fixed all-mature refit). Read [the full protocol](../planning/CP2_CORRECTED_MODEL_CANDIDATES_V5.md) before rebuilding. Existing v1 artifacts stay frozen; production source pins are unchanged.
