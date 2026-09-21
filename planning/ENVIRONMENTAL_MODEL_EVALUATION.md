# Environmental factors in the warranty-risk experiments

## HOTOSM waterways source

The project now uses the 9 September 2026 HOTOSM Malaysia waterways snapshot,
sourced from OpenStreetMap and distributed through HDX under ODbL. The exact
source ZIP is pinned by SHA-256
`544664dd486c2b2b8471c8ba2092f879dfa6282406943cf3a211cbdd0853c513`.
The bounded service-region load contains 56,582 water features.

Derived fields distinguish drainage (drains, ditches and canals), flowing water
(rivers and streams), and standing water. They include nearest distance and
feature counts within 500 m, 1 km and 2 km. All 1,119 cached service locations
have a mapped waterway within 2 km, compared with 951 locations in the earlier
Geoapify result. This is improved mapped coverage, not evidence that a location
flooded. OpenStreetMap completeness varies with volunteer mapping activity.

## Residential 3x model

| Feature contract | Pre-2026 mean ROC AUC | Mean AP | Mean Brier |
|---|---:|---:|---:|
| v3 base | 0.5198 | 0.2540 | 0.2145 |
| Legacy static environment | 0.5165 | 0.2496 | 0.2194 |
| HOTOSM waterways | 0.5090 | 0.2409 | 0.2239 |
| All static environment | 0.5112 | 0.2404 | 0.2264 |

HOTOSM waterways worsen all three pre-2026 mean metrics for the 3x target. They
must not be added to the selected 3x contract. Small gains in the already-inspected
2026 diagnostic do not override the development result.

## Residential 4x/6x/12x repeated-coverage model

| Feature contract | 2026 ROC AUC | Average precision | Brier |
|---|---:|---:|---:|
| Base | 0.6607 | 0.2473 | 0.2133 |
| Prior weather | 0.6440 | 0.2582 | 0.2227 |
| HOTOSM waterways | 0.6863 | 0.2786 | 0.2050 |
| Weather and HOTOSM | 0.6603 | 0.2421 | 0.2174 |

Waterways initially improve the simple temporal benchmark, but that gain does
not survive the stronger test. After prediction-safe prior history is added and
packages are separated across grouped folds, history-only mean ROC AUC is 0.6522
and average precision is 0.2907, while history plus HOTOSM falls to 0.5424 and
0.2132. HOTOSM therefore remains descriptive context and is not selected.

## Flood-event source decision

ReliefWeb is suitable for broad event-date and named-area context after an
approved API `appname` is obtained. Its disaster records do not provide consistent
property-level flood footprints, so they must not be used to label a service
property as flooded. Any future ReliefWeb feature must be framed as reported
regional flood context.

Reproduce the waterway load and comparisons with:

```powershell
python scripts/load_hotosm_waterways.py
python scripts/evaluate_warranty_environmental_factors.py
python scripts/evaluate_warranty_coverage_episodes.py
```
