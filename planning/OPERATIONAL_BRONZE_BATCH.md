# Complete operational Bronze batch

Run from the activated project environment:

```powershell
python scripts/load_operational_bronze.py --upload
```

Without --upload, the script reads the live sources and checks layouts only.
The existing private NOMOBUG_BQ_UPLOAD_APPROVED=yes setting is required for writes.
No source edits, raw disk exports, automatic deletion, Neon writes or Silver builds.

All eight operational layouts and row positions are validated before uploads begin. Sheets
are read sequentially, not as a simultaneous source transaction. Each content hash
includes source ID, tab, header position, original headers and every returned row.
The original extraction time stays with reused content. Row positions are snapshot
lineage, not permanent transaction identifiers. Do not sum across snapshot history.

Each table load uses WRITE_EMPTY and is independently atomic; the three-table
batch is NOT atomic. If a later load fails, earlier Bronze tables may exist.
Rerun safely verifies/reuses identical tables; do not delete them. Run one loader
at a time. Five snapshots per source and 100 MiB per source payload are safety
gates, not billing caps. Dataset expiry/region are checked before any upload.

All raw values are preserved as strings, including #VALUE! headers, repeated
invoice headers, blank headers, placeholder rows and duplicate payment entries.
PAYMENTS amounts are not parsed or allocated in Bronze.

The loader prints all eight exact table identities after verification. This batch
also includes PAYMENT LINK, WARRANTY CLAIM, Commercial Clients, REFUND and
Recurring Payments. No automatic latest-table selection or partial-batch Silver
publication is implemented.

Learning path: read load_operational_bronze.py for the sequence, the source
contracts for header checks, and operational_bronze_core.py for hash/load/verify.
Small helper functions keep cloud calls mockable; the runner remains top-to-bottom.
