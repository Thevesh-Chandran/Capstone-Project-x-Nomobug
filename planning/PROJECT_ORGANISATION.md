# Current organisation

The current [folder guide](../project_guide/Project_Structure.md), [file catalogue](../FILE_GUIDE.html) and [supervisor notebooks](../notebooks/README.md) supersede the navigation below. The rest is dated historical cleanup evidence, not current website status.

# Project organisation — 16 October 2026

Start at `START_HERE.md`. Current project root is Desktop, outside OneDrive.

## Cleanup performed

Removed regenerable Python caches and dbt compilation/log artifacts. Full inventory is in `outputs/project_audit/20261016_cleanup/local_cleanup.json`. NTFS compression is applied to retained data and outputs to reduce physical disk use without changing contents or filenames.

Frozen bundles, prediction receipts, declared protocols, source snapshots and release evidence are retained. Similar dated snapshots are not automatically duplicates: different releases need their own provenance. Existing code paths remain stable rather than silently invalidating the running system.

## BigQuery

Use `gold` for dashboard-facing sources, `silver` for transformations, `bronze` for original snapshots, `analytics_ml` for model research and `audit` for run evidence. Friendly display names and `cp2_role` labels clarify their purpose. Datasets prefixed `cp2r_` are versioned release evidence; `cp2qa_` are historical validation. These are not alternate dashboard sources.

No dataset is deleted solely because its name looks old. The catalog captures the stable Gold view SQL so dependencies can be checked before retiring releases. Existing ID references and permissions are preserved.

## Dashboard design

Current preview: `outputs/dashboard_design/20261014_complete_system/index.html`.

The October 4 guide and October 12/14 alternative designs are historical. Dated acceptance/redesign-live folders contain verification evidence rather than competing current mockups. They remain at their original paths so existing references work. Current Looker report editing remains with the owner.

## Next implementation

After cleanup verification: revise the complete-system mockup for pest-return and sales heatmaps, private individual-location drill-down, proximity groups and honest area-level model evaluation. Operational hotspot rates and model performance must use separate populations. Geography must not be chosen to manufacture the highest reported accuracy.

## Completed storage result

NTFS reports 3,963,120,396 data bytes stored in 2,911,448,951 bytes, and 2,645,055,346 output bytes stored in 767,316,124 bytes. Combined reduction: 2,929,410,667 bytes (2.93 GB decimal). Disposable artifacts removed: 45,904,410 bytes. These figures are reduction from logical uncompressed size, not a measured whole-disk before/after free-space delta.

32 focused website tests passed after the move. All eight local links in the refreshed initial start guide resolved. BigQuery metadata operations labelled 77 datasets; 42 stable Gold objects were catalogued. No cloud datasets were deleted, because retention/dependency evidence does not yet establish that historical releases are disposable.

## Spatial preview started

`outputs/dashboard_design/current_spatial_preview/index.html` is a new local prototype from the approved saved snapshot: 1,263 located purchases and 913 located Calendar warranty signals, plus the separate 100-service historical model evaluation. It includes proximity cells, zoom, point inspection, date filtering and per-cell model evidence. These are not deployed maps. Warranty signals must not be labelled verified recurrence or formal claims. Cells require at least 20 services and five positives for performance colouring; these are conservative display gates, not validation of a subgroup. The prototype uses grid cells, not DBSCAN, and does not yet support map panning or production uncertainty-aware selection. JavaScript syntax checks passed. Browser visual verification was blocked by the browser file-URL security policy; it was not bypassed.

## Protected SQL correction

The full suite identified eight frozen collector SQL files under `dbt/target` as runtime inputs. They were restored from the immutable cloud artifact inventory, with both byte and normalized SQL hashes verified. The cleanup utility now protects `dbt/target`. No cloud artifacts or model weights were changed. See `outputs/project_audit/20261016_cleanup/frozen_sql_restore.json`.
