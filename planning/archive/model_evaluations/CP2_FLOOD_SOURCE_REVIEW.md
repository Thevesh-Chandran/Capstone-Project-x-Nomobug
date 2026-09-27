> Archived evidence or implementation history. Its dated status and model choices are not current instructions. Start with [the current model guide](../../CP2_START_HERE.md).

# CP2 observed-flood source and method review

Reviewed 27 September 2026. This is a source and feature-method review, not evidence that flooding improves callback prediction.

## Source selected

Copernicus Emergency Management Service Global Flood Monitoring (CEMS GFM), distributed by EODC through its public STAC catalogue. GFM maps observed floodwater from Sentinel-1 radar imagery using an ensemble of three algorithms. Its nominal pixel sampling is 20 m; that is not a guarantee of 20 m detection accuracy. Use the observed ensemble flood extent, rather than permanent water or a flood forecast. The official provider demonstrates discovery of the `GFM` collection and its `ensemble_flood_extent` asset through the same catalogue. [EODC discovery tutorial](https://docs.eodc.eu/tutorials/download_gfm_python.html), [Copernicus overview](https://european-flood.emergency.copernicus.eu/news/19th-efas-annual-meeting).

Provider attribution: “Source: Copernicus Emergency Management Service Global Flood Monitoring (CEMS GFM), distributed by EODC.” Preserve the source item identifiers, acquisition and availability timestamps, algorithm version, and derivation settings with the feature receipt. The provider's [terms and conditions](https://extwiki.eodc.eu/GFM/Terms_and_conditions) remain the source reference; this review does not reinterpret their legal terms.

## Spatial interpretation and quality masks

For a 1 km circular buffer around a geocoded customer location, calculate flooded-pixel fractions only among reliable observed land pixels. Require a valid flood class, a clear exclusion mask, no reference permanent or seasonal water, and no advisory flag. The exclusion layer identifies surfaces where radar flood detection is unreliable, including dense vegetation, urban surfaces, terrain distortions and radar shadow. Its no-sensitivity masking principally affects non-flooded classifications. Masked pixels are unknown, not dry. Reference water is normal water, not a new flood. [GFM output layers](https://extwiki.eodc.eu/GFM/PUM/Products).

Advisory values identify low regional backscatter, rough water, or both; these are separate from the exclusion mask. Excluding flagged pixels is our conservative modelling choice. It sacrifices coverage to reduce uncertain classifications. Do not use the catalogue's `anomaly_detected` flag as a quality rejection: it indicates an unusually large tile-level flood amount relative to past observations. [Technical layer definitions](https://extwiki.eodc.eu/en/GFM/PDD/GFM_Product_Output_Layers), [Copernicus anomaly explanation](https://global-flood.emergency.copernicus.eu/news/169-minor-gfm-update-for-the-visualization-of-the-anomaly-detection/).

At least two ensemble algorithms must contribute. Official ensemble guidance says a single available algorithm is insufficient and the output should become no data. Mask values outside their documented classes must also stay unknown. [GFM ensemble method](https://extwiki.eodc.eu/GFM/PUM/Algorithms/Algorithm4).

Implementation requirements:

- Raster reads must use the native georeferencing, correct axis order, and a projected metre coordinate system. A latitude/longitude degree buffer is not a 1 km circle.
- All contributing layers must align in shape, transform and coordinate reference system. Never silently pair different windows or different scene items.
- Calculate valid coverage relative to the full intended buffer, including no-data and tile-boundary gaps. Suppress flood fractions when fewer than 50% of buffer pixels are reliable observed land pixels. This 50% threshold is a predeclared analysis policy, not a provider quality guarantee.
- A buffer straddling adjacent tiles requires combining those tiles without double counting. Treating either partial tile as the full area overstates coverage; failing to combine can conservatively reduce availability.
- Retain observation counts, valid fraction and age of latest usable observation. Missing source coverage, failed retrieval, excluded terrain, advisory flags and normal water must remain distinguishable from an observed zero flood fraction.
- A small positive fraction can represent genuine nearby flooding or classification error. Prefer continuous fractions; any binary threshold must be stated, fixed before evaluation, and supported by a sensitivity check.

## Time and availability rules

Only use scenes acquired before the prediction anchor, and only when their recorded creation and processing timestamps also precede that anchor. Where a service has only a date, use midnight at the start of that date in Asia/Kuala_Lumpur. This deliberately excludes same-day scenes because the time of prediction cannot be established reliably. Parse timestamps as timezone-aware instants; converting a UTC timestamp directly to a date can cross the Malaysian date boundary.

Use `max(created, processing:datetime)` as the conservative recorded availability time. It is an availability proxy from the current catalogue, not proof of the first historical publication time or a guarantee that every ancillary mask version was available at that instant. Reprocessed scenes are retrospective data and must not enter a prior prediction merely because their satellite acquisition was earlier. STAC distinguishes acquisition time from creation metadata. [STAC common metadata](https://github.com/radiantearth/stac-spec/blob/master/commons/common-metadata.md).

Features summarize usable observations in the previous 7, 14 and 30 days, including maximum observed flood fraction and days since the most recent observed flooding. They do not measure flood duration or the maximum physical extent between satellite passes. When no usable observation exists in a window, flood fractions and recency remain null. Counts can be zero as a statement about observation availability. The capped recency field is 30 when there are usable observations but no detected flooding in the lookback: this is a censored “no detection in available observations” category, not a known flood date 30 days ago or proof that flooding was absent.

## Local catalogue audit

The preliminary cached discovery receipt `tmp/gfm_catalogue_full.json` contains 3,880 items for the requested Malaysian bounding box, 100.3°E–104.1°E and 1.4°N–5.8°N. Sensing dates range from 1 February 2024 to 14 August 2026 across seven Equi7 tiles. The following counts describe this preliminary query, not the full global GFM archive or the final extraction catalogue. The initial metadata projection retained three asset types. The extraction script now queries all four required layers, including advisory flags, for a bounding box derived from the eligible anchors; its final receipt is authoritative for extraction coverage.

| Sensing year | Items | Median recorded availability lag | Items with lag over 7 days |
|---|---:|---:|---:|
| 2024 | 1,220 | 90.383 days | 946 |
| 2025 | 1,631 | 0.166 days | 12 |
| 2026 | 1,029 | 0.173 days | 4 |

Lag is `max(created, processing:datetime) - datetime` calculated from saved item properties. The minimum catalogue creation timestamp is 31 October 2024. There are 264 items labelled `archive V02`; these explain part, but not necessarily all, of the long historical delays. Conservative availability gating therefore removes many otherwise geographically relevant 2024 scenes. It is incorrect to treat the resulting missing flood features as evidence that those places did not flood.

Algorithm contribution counts are 3,702 items with three members, 176 with two, and two with one. Product versions are mixed: GFM v3.1.0, v4.0.0, v4.1.0 and v4.1.1. Preserve them in extraction provenance. `anomaly_detected` is true for 1,055 items, false for 2,792, and absent for 33; it must not be interpreted as the local property's flood status.

The subsequent four-asset extraction catalogue contains 3,864 scenes. Twenty-five genuinely lack a required source layer: 17 lack the exclusion mask and eight lack advisory flags. Requesting all layers does not ensure every source scene supplies them. Relevant incomplete scenes are rejected before raster download; temporally or geographically irrelevant scenes are skipped. The receipt distinguishes missing quality layers from retrieval/extraction errors, and potentially affected anchors retain an explicit source-error status. A cached catalogue is validated against the requested asset projection, date range and query area; genuinely incomplete provider items must not trigger endless catalogue refreshes.

## Limits for the CP2 prediction question

GFM detects exposed floodwater near a location. It cannot confirm that a customer's building flooded, show water depth indoors, distinguish pest displacement from treatment failure, or establish causation. Urban and vegetated properties may have especially weak radar sensitivity, even when the surrounding buffer has some valid pixels. Addresses and geocoding accuracy also limit spatial interpretation.

Coverage changes over time. Sentinel-1C was integrated into GFM on 28 October 2025, increasing observation opportunities, while algorithm updates also alter detection. Availability indicators may therefore act as proxies for the service date or geographic coverage rather than actual flooding. [Copernicus Sentinel-1C update](https://global-flood.emergency.copernicus.eu/react/news/223-gfm-now-includes-data-from-sentinel-1c/).

The modelling comparison must keep identical service records, target labels, cutoffs and purged validation groups for versions with and without flood features. Missing flood data should not remove records from one arm. Report coverage, number of exposed callbacks and missingness by period alongside AUC, average precision, calibration and operational ranking performance. Select features and models before inspecting the shared later-period diagnostics. Previously inspected 2026 outcomes remain exploratory; a prospective later-period test is needed before claiming dependable operational improvement.

## Supplementary GDACS reported-region context

GDACS is a separate regional-report source. Its public API permits a Malaysian flood-event query and supplies event details and episode-specific geometry. A query must explicitly include Green, Orange and Red alerts; the default response omitted most Malaysian events during this probe. The implemented query records its endpoint, exact parameters and page results in the source fingerprint. It checks the next page even after a short first page: page 1 returned 38 records and page 2 returned HTTP 204, confirming an empty next page. [Official API](https://www.gdacs.org/gdacsapi/swagger/index.html), [GDACS quick start](https://www.gdacs.org/Documents/2025/GDACS_API_quickstart_v2.pdf).

Only `Poly_Affected` geometry is used. `Poly_Global`, centroids and unrelated geometries are excluded. This is point containment within reported regional areas, without a flood-buffer area estimate. GDACS explicitly says analyst polygons encompass reported affected places and do not delineate the area actually underwater. The feature names therefore describe **reported regional events**, never observed property flooding. [Official Malaysian event report](https://www.gdacs.org/Floods/report.aspx?episodeid=1&eventid=1103572&eventtype=FL).

Historical episode endpoints retain current event modification timestamps. For example, the first and fourth episodes of FL-1103130 both carry the current 10 March 2025 modification timestamp, while their affected polygons carry different February/March dates. We do not infer earlier publication from the polygon date. Availability is conservatively approximated by the latest event, geometry or detail modification timestamp and all supplied Sendai insertion timestamps. Timezone-naive availability fields receive an additional 24-hour delay. Both this availability proxy and the polygon event timestamp must precede Malaysian anchor midnight. This is conservative retrospective gating; it does not verify immutable historical publication of every polygon version.

The four numeric features are distinct event counts for prior 7, 14 and 30 local days and capped days since the latest matching reported event. Counts deduplicate event IDs. A fully queried record with no matching region has zero **matching recorded reports** and censored recency 30; these do not prove dry conditions. Missing coordinates or incomplete query-period coverage produce null counts and null recency. Any public-source fetch failure stops upload rather than silently assigning negatives.

The final GDACS extraction loaded 5,598 anchors and 38 affected polygons, with no source errors. Matches are sparse: 123 of 640 anchors in 2024, three of 2,983 in 2025, and none of 1,975 in 2026. Thus these particular features cannot distinguish flood exposure among the evaluated 2026 anchors. Their older-period values may instead reflect geography, reporting detail and conservative publication delays. A model score change after adding them must not be presented as evidence of useful 2026 flood-risk discrimination.

Reproduce discovery and extraction with `python scripts/fetch_gdacs_flood_context.py`; the default uses the bounded official query and public cache. Replay the frozen discovered catalogue with `--events-json data/processed/environment/gdacs/events_catalogue.json`. The source snapshot and receipt include query provenance, selected geometry, the availability policy and a SHA-256 digest. Customer coordinates are evaluated locally and are not sent to GDACS. Attribution: “Global Disaster Awareness and Coordination System, GDACS.”
