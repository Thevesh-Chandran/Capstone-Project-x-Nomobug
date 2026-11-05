# Current warehouse catalogue · 25 October 2026

Open `gold.READ_ME` for reporting and `analytics_ml.READ_ME` for model research. Readable display names/descriptions are applied to 33 datasets and 196 existing stable objects; IDs, data and permissions are preserved. [Object catalogue](../project_guide/BigQuery_Catalogue.csv). Earlier cleanup counts below describe 16 October only; new release datasets have since been created.

# BigQuery — start here

For management reporting, open the **gold** dataset (friendly name: **01 — Management reporting**), then **READ_ME**.

| Source to use | Purpose |
|---|---|
| gold.sales | Recorded sales and package prices |
| gold.customers | Customer reporting |
| gold.appointments | Scheduled Calendar visits |
| gold.payment_reminders | Staff reminder dates and recorded contract balances |
| gold.payment_data_checks | Missing dates and payment data coverage |
| gold.refunds | Recorded refund reporting |
| gold.team_schedule | Team and technician bookings |
| gold.area_sales | Sales records with location fields; aggregate by area when charting |
| gold.model_results | Aggregate experimental model evaluation |

These readable views point to the existing stable approved dashboard sources. Existing source IDs remain for application compatibility. Technical IDs are not renamed in place: BigQuery datasets cannot be directly renamed. No reporting calculations or sharing permissions changed.

Other datasets: silver = cleaned records; bronze = immutable sources; analytics_ml = research and model evidence; audit = release/prediction logs; quality = data checks. Three retained release pairs support current reporting, recent rollback and a pinned dependency. archived_reporting_releases = recovery snapshots, not a reporting source.

## Cleanup completed 16 October 2026

78 datasets reduced to 13 by removing 66 obsolete release/QA datasets and adding one archive. All 303 physical tables in removed datasets have archive snapshots, with row counts verified before deletion. Dataset/table/view definitions and removal receipt are saved locally under outputs/project_audit/20261016_bigquery_cleanup and privately in gs://cp2-portal-profound-keel-500007-s4/archive/bigquery_cleanup_20261016/.

47 current Gold views passed dry-run dependency checks after cleanup. Preserved dependency roots include stable datasets, current source/configuration/code and recent rollback definitions. Looker-labelled job references were checked over two days. The requested 30-day metadata query exceeded the 100 MiB query ceiling and was blocked; it was not rerun at a higher limit. Dormant external queries are not exhaustively discoverable; a direct historical release reference may require restoration.

## Recovery

The utility scripts/restore_archived_bigquery_release.py previews restoration with --dataset DATASET_ID; add --apply to restore. Restore physical tables and paired silver/gold view definitions before querying dependent views. Review the backed-up original access configuration when restoring custom access. No source facts, model weights, thresholds or prospective prediction timestamps were altered by this cleanup.

The cleanup utility is dated to this inventory; it is not an automatic daily retention policy. Future releases still receive unique technical names. Repeat dependency review and refresh inventory before later cleanup.
