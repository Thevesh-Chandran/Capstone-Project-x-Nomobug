# Website refinement — 16 October 2026

Scope: private website, heatmaps, wording, operation checks and CI. The owner asked that Looker Studio be left alone; no dashboard editing is part of this checkpoint.

## Changes

- A more compact map layout brings the map higher on the screen. The top-area list sits beside it, rather than below a largely empty detail panel.
- Sales heat colours now come from an accumulated, sales-weighted density field. Warranty heat uses visit counts. Location uncertainty spreads each contribution, with a minimum smoothing radius; colours are relative to the visible map, not absolute risk or a recurrence rate. The colour legend is above the map. Groups still use the existing conservative location-boundary checks.
- Heatmap area overlays can be selected without switching views. The list opens the same group, and group zoom reveals individual mapped records. Unknown area labels use their approximate centre instead of repeating “Mapped area”; duplicate state/district labels are shortened.
- The main Area explorer link opens the actual map. The coordinate/radius comparison remains available through Back to workspace and automatically fills its default comparison.
- The home page exposes all six tools: dashboard, area explorer, customers, payment follow-up, assistant, model/system. These are compact tool cards with short descriptions.
- Payment actions use plain language instead of internal source codes. The balance filter has a simpler label. The model page reads the recovery evaluation date from its actual registry field.
- Snapshot downloads reject mismatched reporting releases before replacing local files, preserving last-good data. The reporting deployment workflow now preserves the website export setting, and CI includes a website container import smoke check.

## Verification

- 575 Python tests passed, with 19 existing rasterio deprecation warnings. Two new tests cover mixed-release and download-failure preservation followed by successful recovery.
- JavaScript syntax checks passed for maps, application and workspace tools. Workflow YAML parsed locally; remote GitHub Actions were not dispatched in this checkpoint.
- Real-data API acceptance passed against `cp2r_202610152200214c6271`, including auth, source totals, customer programme links, payments, radius changes and invalid dates.
- Live browser: CUST1412 search returns the confirmed programme; map point CUST2101 opens one matching customer group; 39 payment contracts load; upcoming and missing-date filters return 7 and 10 contracts respectively as of 16 October. Payment totals remain RM26,461 recorded paid and RM74,545 remaining, rounded.
- Sales, warranty and historical model layers load; hotspot selection, group zoom, individual record inspection and direct customer history links work. The custom 5 km comparison auto-loads 6 purchases, 37 appointments and RM3,576 known recorded sales for the displayed period.
- Hosted recovery execution `cp2-portal-recovery-check-twm5v` succeeded. Using the existing read-only portal identity, it downloaded the five private snapshots, deliberately requested a missing prefix, verified all prior file hashes stayed unchanged, then successfully refreshed from the correct prefix. Only generic status was logged. The temporary job was deleted after evidence was saved.
- No customer data or credentials were added to the image. No frozen model, threshold, prediction receipt or cohort protocol changed.

## Open items

Client M and Hotel client H remain on [the owner review list](CP2_OWNER_REVIEW.md); the owner will check later. This checkpoint does not prove broad Ollama reasoning reliability or future model performance. Looker remains outside the requested scope.

Evidence: `outputs/project_audit/20261016_final/hosted_refresh_recovery_result.json`, `outputs/portal_acceptance/20261016/api_acceptance_refinement.json`, and saved browser screenshots. Private audit directories must not be published wholesale.

## Final deployed release

Build `6f0c4cc3-0102-47b5-b213-96e726af788e` passed the container import smoke. Revision `cp2-portal-00025-j2x` serves 100% of traffic; `cp2-portal-00024-srz` is the immediate rollback reference. All six home-page cards and the final heatmap were verified in Chrome. Proof: `outputs/project_audit/20261016_final/website_home_refined.jpg` and `heatmap_refined_live.jpg`.

The final deployment command took substantially longer than expected; its success and new revision were checked rather than inferred from the submitted command. No changes to service identities, source credentials, IAM or frozen experiment artifacts were made.
