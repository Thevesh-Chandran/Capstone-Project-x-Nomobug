# Environmental features: sources, coverage and timing

Receipt date: 27 September 2026. These features describe environmental exposure
around recorded service locations. They do not establish that a property flooded,
that pests recurred biologically, or that treatment failed. The model outcome is
a recorded claim/corrective visit; contractual warranty entitlement is separate.

## Source and timing contract

| Source | Features | Historical timing limit |
| --- | --- | --- |
| Open-Meteo ECMWF IFS historical archive | Prior 1/3/7/14/30-day precipitation; wet/heavy-rain days; recent temperature, humidity and soil moisture; rain trend and rain recency | Every weather date is strictly before the service anchor. The retrospective archive is not a record of the exact weather values available to staff on that historical date. |
| ESA WorldCover 2021 v200 | Tree, grass, cropland, built-up, permanent-water and wetland/mangrove pixel fractions in approximate circular 250 m and 1 km buffers | The map describes 2021 and was released in October 2022, before the 2023+ service dates. It can miss later development, vegetation changes and drainage work. |
| HOTOSM Malaysia waterways, 9 September 2026 | Mapped drainage/flowing/standing-water proximity and counts within 500 m, 1 km and 2 km | This 2026 OpenStreetMap snapshot is applied retrospectively to earlier services. It is not an archived map known to have been available at a 2025 prediction anchor. |
| Geoapify environmental places and elevation | Mapped water/forest proximity and counts; elevation and local relief | Places are current OpenStreetMap-derived context without per-feature historical validity in this pipeline. Terrain is treated as broadly static; neither source confirms past floods or drainage condition. |

The weather cache covers 18 December 2022 through 14 September 2026, using 52
requested 0.1-degree grid locations. This corresponds to broad weather exposure,
approximately 9–11 km, rather than property rainfall. IFS updates and historical
reconstruction can change the source across time. A future operational test
should preserve retrieval timestamps and use data actually available at scoring
time. [Open-Meteo documentation](https://open-meteo.com/en/docs/historical-weather-api).

The new weather model requires complete, unique daily rows and nonmissing inputs
for the relevant window. Incomplete windows yield null feature values rather
than zero rainfall. Rain recency is capped at 30 days only for complete windows.
`prior_7d_temperature_max_c` is the maximum of cached daily **mean** temperatures;
it is not an observed daily maximum. The 2022 cache start cannot support a full
30-day window for the earliest January 2023 services.

WorldCover uses native classified pixels, with no interpolated class labels.
Wetland combines herbaceous wetland class 90 and mangrove class 95. Classification
error remains even when pixel coverage is complete. Missing/unclassified pixels
reduce coverage; fractions are null below 95% valid pixels. Zero fractions at
adequate coverage mean no pixels of that mapped class were counted, not proof
that the real environment lacks it. [ESA source and licensing](https://esa-worldcover.org/en/data-access).

## Bounded WorldCover receipt

The enrichment selected 500 of 1,135 distinct eligible coordinates, prioritising
coordinates used by more fixed-horizon anchors, with a deterministic hash tie
break. Extraction succeeded for all 500 locations at both radii: zero failures,
3.64 MiB downloaded in 58.6 seconds. The quality table is
`quality.worldcover_2021_context_by_location`; the source is `landcover_quality`.

| Initial fixed-horizon population | Period | Anchors | WorldCover-enriched anchors |
| --- | --- | ---: | ---: |
| Residential 3x final-service target | Pre-2026 | 914 | 486 |
| Residential 3x final-service target | 2026 | 434 | 230 |
| Residential 4x/6x/12x after-service target | Pre-2026 | 222 | 220 |
| Residential 4x/6x/12x after-service target | 2026 | 171 | 170 |

These counts describe the initial 1,741-anchor extraction receipt. Later target
or matching changes require a new coverage calculation. Unselected coordinates
remain null through a left join. The 500-location selection favours repeat-use
locations, so results for the enriched subset need not represent all customers.
Keep selection fixed during candidate comparisons and report missingness.

## Spatial uncertainty and retrospective map sensitivity

Service geocodes have stated uncertainty from 250 m to 10 km, depending on their
source and precision tier. A 250 m land-cover buffer or nearest-drain distance
can therefore be more precise than its input location. Nonmissing proximity
does not establish fine location accuracy. Treat coarse-geocode features as
regional context and compare results for better-localised addresses separately.
Changing a map radius does not improve the native weather resolution.

OSM feature counts depend on mapping completeness and geometry fragmentation.
They are not water volume or drainage quality. Geoapify place responses may be
capped at 100 results. The HOTOSM ZIP is SHA-256 pinned, making the current
experiment reproducible, but pinning does not make a 2026 map historically
available in 2025. Candidate improvements using those maps need an explicit
retrospective-static-context limitation and a sensitivity comparison excluding
current OSM features. WorldCover and prior-weather-only variants provide a
cleaner historical timing comparison.

## Flood-event decision

ReliefWeb can supply reported disaster dates and broad named-area context after
an approved API appname is obtained. Its disaster date field is `date.event`;
the earlier proposed `date.start`/`date.end` disaster example does not follow
the documented disaster schema. API filters use the v2 endpoint, not the public
ReliefWeb homepage. [API documentation](https://apidoc.reliefweb.int/),
[documented fields](https://apidoc.reliefweb.int/fields-tables).

A report about a flooded district does not confirm that a particular service
property flooded. Any regional flood feature must respect publication time
(report available before the anchor), spatial coverage and reporting gaps.
Rainfall, waterway proximity, standing-water land cover and disaster reports
must remain distinct variables. No property flood indicator has been added.
