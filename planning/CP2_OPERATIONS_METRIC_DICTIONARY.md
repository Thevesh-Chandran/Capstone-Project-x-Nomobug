# CP2 operations, geography, weather and quality metrics

This dictionary explains the aggregate operational fields available to Nomobug management. Use it with the [dashboard build guide](CP2_DASHBOARD_BUILD_GUIDE.md). Connect Looker Studio to stable views in `profound-keel-500007-s4.gold`; those names follow the latest validated reporting release.

The central distinction is the unit being counted. A Calendar event is a scheduled or recorded visit. A sales record is a package record. A formal claim-sheet row is a claim record. An address group is a property candidate. These units cannot be exchanged or added together. Calendar status `confirmed` is a scheduling status; it does not prove that a technician completed treatment.

## Rules for calculations and filters

- Use `SUM` for event counts when the source groups are disjoint. Calculate percentages from summed numerators and denominators, rather than averaging row percentages.
- Display a ratio as a percentage in Looker: a stored value of `0.10` means 10%. Do not multiply by 100 and also apply percentage formatting.
- Preserve missing values and review categories. A missing location, amount, date or weather window means unknown; it does not mean zero.
- Distinct package/property counts can overlap between groups. Do not sum them into a company-wide unique-customer count.
- Apply a date control only where the source has the relevant date/month field. Different sources require their own date-range dimensions and verification. Geography and treatment-review summaries currently have no date column.
- The operational reporting scope is 2026. Some sources include future scheduled events within 2026. Their counts remain scheduled activity, even for past dates.
- Build date, Calendar, pest, package and radius controls only where those dimensions actually exist. A control on one source does not create a missing dimension in another.
- If a denominator is zero, the share is blank/undefined. Preserve that result instead of calling it 0%.

## Service activity

Source: [dashboard_service_monthly.sql](../dbt/models/gold/dashboard_service_monthly.sql). One row represents one `service_month`, the first date of a month in 2026. Its base is [calendar_service_event_facts.sql](../dbt/models/gold/calendar_service_event_facts.sql): confirmed service-like Calendar entries after cancellation/admin rules and reviewed warranty classifications.

| Field | Plain meaning and unit | Aggregation or use |
|---|---|---|
| `service_month` | Calendar visit month, Malaysia local date | Date-range dimension; month axis |
| `scheduled_service_event_rows` | Number of scheduled/recorded service-like Calendar entries | SUM; label **Scheduled visits** |
| `normal_package_service_event_rows` | Entries classified as normal package service | SUM |
| `warranty_claim_event_rows` | Entries with a recorded warranty signal: explicit/reviewed warranty label or post-package sequence such as 4/3 | SUM; label **Recorded warranty visits** or **Warranty-signal visits** |
| `generic_complimentary_event_rows` | Complimentary entries without a warranty signal | SUM; not automatically corrective callbacks |
| `matched_sales_event_rows` | Entries linked to a sales-package record | SUM |
| `unmatched_sales_event_rows` | Entries without a resolved sales-package link | SUM; records for linkage review |
| `heatmap_eligible_event_rows` | Entries with a location candidate acceptable for aggregate mapping | SUM; location coverage numerator |
| `heatmap_eligible_warranty_claim_rows` | Warranty-signal entries among location-eligible events | SUM |
| `warranty_claims_with_complete_prior_14d_weather` | Warranty-signal entries with all previous 14 weather days available | SUM; weather coverage numerator for warranty signals |
| `warranty_claim_event_share` | Warranty-signal entries / all scheduled entries in that month | Recalculate after combining months |
| `heatmap_warranty_claim_share` | Location-eligible warranty signals / all location-eligible entries | Recalculate after combining months |
| `denominator_evidence` | Text explaining what the denominator represents | Explanatory label, not a measure |

Useful calculated measures:

| Label | Calculation |
|---|---|
| Warranty-signal share | `SUM(warranty_claim_event_rows) / SUM(scheduled_service_event_rows)` |
| Sales-link coverage | `SUM(matched_sales_event_rows) / SUM(scheduled_service_event_rows)` |
| Location coverage | `SUM(heatmap_eligible_event_rows) / SUM(scheduled_service_event_rows)` |
| Warranty weather coverage | `SUM(warranty_claims_with_complete_prior_14d_weather) / SUM(warranty_claim_event_rows)` |
| Mapped warranty-signal share | `SUM(heatmap_eligible_warranty_claim_rows) / SUM(heatmap_eligible_event_rows)` |

For a stacked activity chart, use normal package entries, warranty-signal entries, and **Other scheduled entries** calculated as `scheduled_service_event_rows - normal_package_service_event_rows - warranty_claim_event_rows`. Current [calendar_events.sql](../dbt/models/calendar_events.sql) makes normal service and warranty categories mutually exclusive. Other entries retain complimentary/additional scheduling activity. A warranty Calendar entry and a formal warranty-claim sheet record remain different grains.

Management can use these measures to understand workload and warranty demand, then review unusual patterns. They do not establish completed jobs, unique customers, reinfestation or contractual warranty eligibility.

## Scheduled workload by Calendar/team

Source: [dashboard_scheduling_capacity.sql](../dbt/models/gold/dashboard_scheduling_capacity.sql). One row represents `service_date × calendar_name × day_of_week_number` in 2026. The name describes the recorded Calendar, which can correspond to a team. It is not a validated individual-technician identity.

| Field | Meaning and unit | Use |
|---|---|---|
| `service_date` | Scheduled visit date, Malaysia local date | Date control; daily trend |
| `calendar_name` | Source Calendar/team label | Bars or table rows; page-specific filter |
| `day_of_week_number` | BigQuery weekday: 1 Sunday, 2 Monday, …, 7 Saturday | Map to weekday names and sort intentionally |
| `scheduled_event_rows` | Number of service-like scheduled/recorded entries | SUM; workload measure |
| `normal_package_event_rows` | Normal package-service entries | SUM |
| `warranty_claim_event_rows` | Recorded warranty-signal entries | SUM |
| `generic_complimentary_event_rows` | Complimentary entries without warranty signal | SUM |
| `extra_visit_signal_rows` | Warranty, complimentary and other extra-visit-candidate entries | SUM; overlaps warranty/complimentary categories |
| `matched_sales_event_rows` | Entries with a resolved sales link | SUM |
| `unmatched_sales_event_rows` | Entries without a resolved sales link | SUM |
| `ambiguous_sales_event_rows` | Entries whose sale matching remains ambiguous | SUM; included within linkage exceptions |
| `denominator_evidence` | Scheduled workload interpretation | Explanatory text |

Use a daily trend, Calendar workload bars and a weekday-by-Calendar heat table. Keep warranty rows as a review/workload component. Do not stack `extra_visit_signal_rows` beside warranties as disjoint categories. Management can redistribute upcoming appointments after inspecting busy dates, or correct ambiguous links.

The view does not supply available staff hours, completed treatment hours, visit outcomes, travel time or cancellation counts. Therefore capacity utilisation, completion rate, travel efficiency and technician success rankings are unavailable.

## Recorded warranty return intervals

Source: [dashboard_recurrence_monthly.sql](../dbt/models/gold/dashboard_recurrence_monthly.sql), built from [dashboard_recurrence_windows.sql](../dbt/models/gold/dashboard_recurrence_windows.sql). One aggregate row represents `service_month × recurrence_bucket × recurrence_reason`.

The interval compares a later warranty-signal entry to the immediately preceding matched service-like Calendar entry for the **same sales package and exact normalized address text**. The earlier entry can itself be a warranty visit. This interval is not uniformly time since the last paid service and is not the frozen model's callback incidence denominator. Address wording differences may split the same physical property; missing address text remains isolated for review. This view uses events dated on or before the current Malaysia date.

| Field | Meaning | Use |
|---|---|---|
| `service_month` | Month of the later warranty-signal entry | Date/month control |
| `recurrence_bucket` | Interval or review category listed below | Ordered bars; monthly stacked chart |
| `recurrence_reason` | Recorded warranty classification reason, such as explicit label, post-package sequence or manual review | Explanatory breakdown |
| `recorded_warranty_signal_rows` | Number of later entries carrying a warranty signal | SUM |
| `property_text_available_rows` | Signal rows with address text available for property grouping | SUM |
| `property_review_rows` | Signal rows without address text | SUM; keep visible |
| `denominator_evidence` | Recorded signals rather than confirmed reinfestations/unique customers | Explanation |

| Bucket | Meaning |
|---|---|
| `0_7_days` | 0–7 days since the preceding matched event |
| `8_14_days` | 8–14 days |
| `15_30_days` | 15–30 days |
| `31_60_days` | 31–60 days |
| `61_plus_days` | At least 61 days |
| `no_previous_event` | No earlier event in this package/property group |
| `property_needs_review` | Address text unavailable |
| `invalid_interval_review` | Interval requires review |

Show review categories with counts. A useful table presents bucket, recorded signal count and share of all recorded signal rows. A share within 30 days can sum the first three buckets, with unknown intervals shown separately; label it **Share of recorded returns within 30 days of preceding event**. Do not label it treatment failure rate or 30-day callback probability.

Management can investigate concentrated short-interval returns and documentation consistency. Planned package visits do not enter the return count merely because they repeat at an address.

## Aggregate service-area map

Source: [dashboard_spatial_area.sql](../dbt/models/gold/dashboard_spatial_area.sql), built from [spatial_service_area_metrics.sql](../dbt/models/gold/spatial_service_area_metrics.sql). One row is a geohash-5 `area_cell`, an analytical bin covering several kilometres. It aggregates 2026 events and publishes only cells with at least five scheduled entries.

| Field | Meaning and unit | Use |
|---|---|---|
| `area_cell` | Analytical area code | Map tooltip/table identifier |
| `area_centroid_latitude`, `area_centroid_longitude` | Aggregate centroid of observed eligible locations, degrees | Aggregate map point |
| `scheduled_service_event_rows` | Location-eligible scheduled entries in the cell | SUM across area cells; bubble size |
| `matched_sales_records` | Distinct linked packages observed in the cell | Tooltip; do not sum to unique-company packages |
| `repeat_signal_event_rows` | Location-eligible warranty-signal entries in the cell | SUM; tooltip |
| `warranty_label_event_rows` | Entries classified in the warranty event category | Component count; do not add to repeat signals |
| `over_sequence_event_rows` | Entries with sequence greater than package total, e.g. 4/3 | Component count; can overlap warranty signals |
| `repeat_signal_share` | Repeat signals / scheduled entries in the cell | Map colour; recalculate if combining cells |
| `map_grain_evidence`, `denominator_evidence` | Grain and denominator explanation | Visible note |

Bubble size shows service volume; colour shows recorded warranty-signal share. Show both numerator and denominator in the tooltip. A cell with 1 signal among 5 visits differs materially from one with 20 among 100, even though both are 20%.

Locations remain approximate and can include wider area candidates. Map points and visual bubble sizes do not identify customer premises, service boundaries or pest-spread distances. A linked package can occur in multiple cells, so distinct-package counts overlap.

**No date, pest, package or Calendar dimension exists in this view.** Label the map **2026 published snapshot**. Exclude it from date controls rather than displaying a false filtered result. Low-volume areas withheld from the release mean map totals can be lower than total recorded service activity.

Management can investigate areas with both sufficient service volume and warranty signals, and discuss route planning. The map does not establish neighbourhood outbreaks or causal treatment problems.

## DBSCAN cluster sensitivity

Source: [dashboard_spatial_cluster_summary.sql](../dbt/models/gold/dashboard_spatial_cluster_summary.sql). Underlying [property clusters](../dbt/models/gold/spatial_repeat_signal_property_clusters.sql) use one row per distinct geocoded property with recorded warranty signals. Repeated callbacks at one address do not supply multiple properties toward the minimum cluster size.

The published grain is `radius_km × cluster_id`. DBSCAN clusters require at least three distinct properties. The input uses precise/street coordinate candidates. Non-clustered noise properties are omitted from the cluster summary.

| Field | Meaning and unit | Use |
|---|---|---|
| `radius_km` | DBSCAN neighbour distance: 1, 2 or 5 km | Single-select control; default 2 km |
| `cluster_id` | Cluster label within that radius setting | Table identifier; not a durable area name |
| `cluster_centroid_latitude`, `cluster_centroid_longitude` | Aggregate cluster centroid, degrees | Cluster map |
| `distinct_service_properties` | Distinct property candidates contributing to this cluster | SUM within one radius scenario only |
| `recorded_warranty_signal_rows` | Recorded warranty entries at those properties | SUM within one radius scenario |
| `property_level_sales_package_rows` | Sum of each property's distinct-package count | Context; not global distinct packages/customers |
| `complete_prior_14d_weather_rows` | Signal entries with complete previous-14-day weather | Coverage context |
| `avg_prior_7d_precipitation_mm` | Average of covered properties' mean previous-7-day rain | Millimetres; property-weighted cluster context |
| `avg_prior_7d_relative_humidity_pct` | Average of covered properties' mean previous-7-day humidity | Percent; property-weighted context |
| `avg_prior_7d_soil_moisture` | Average of covered properties' mean previous-7-day soil moisture | Volumetric fraction; property-weighted context |
| `cluster_evidence` | Minimum-property and sensitivity explanation | Visible note |

Show one radius setting at a time, with a cluster table and centroid map. To compare settings, use side-by-side summaries explicitly filtered to 1, 2 and 5 km. Never add all three scenarios into one cluster/property/event total. Cluster IDs are specific to a scenario and may change with source updates.

**Changing the dashboard radius changes the grouping of records. It does not retrain the frozen model or change its reported held-out accuracy.** Radius is not an inferred distance that pests travel.

This source also has no date, pest or Calendar dimension. Label its 2026 snapshot scope. Because noise is omitted and location eligibility is stricter than the area map, its totals will not match all warranty signals or all mapped events.

## Separate service-review indicators

Source: [dashboard_treatment_difficulty.sql](../dbt/models/gold/dashboard_treatment_difficulty.sql). One row is `area_cell × calendar_name × pest_type × package_type`, covering 2026 events. Use the page title **Service review indicators**, since a treatment-difficulty composite has not been validated.

| Field | Meaning | Use |
|---|---|---|
| `area_cell` | Geohash-5 area or `NO_LOCATION` | Group/context |
| `calendar_name` | Source Calendar/team label | Filter/group |
| `pest_type`, `package_type` | Recorded SALES labels; missing values remain blank | Filter/group; compound labels are retained |
| `scheduled_event_rows` | Scheduled/recorded events in the group | Denominator; SUM for disjoint groups |
| `matched_sales_records` | Distinct linked packages within the group | Context; overlaps between groups |
| `warranty_claim_event_rows` | Warranty-signal entries | SUM |
| `extra_visit_signal_rows` | Additional/complimentary signals excluding warranty signals | SUM; does not imply a failed treatment |
| `linked_refund_event_rows` | Event rows belonging to a package with a linked REFUND record | Package context repeated across events |
| `warranty_signal_share` | Warranty entries / scheduled entries | Recalculate from counts |
| `extra_visit_signal_share` | Non-warranty extra entries / scheduled entries | Recalculate from counts |
| `linked_refund_signal_share` | Entries with linked-package refund context / scheduled entries | Not refund incidence per treatment |
| `treatment_difficulty_proxy_0_100` | Unvalidated composite, deliberately null | Do not chart |
| `sufficient_volume_for_comparison` | At least five scheduled entries | Filter true for group comparisons |
| `score_evidence` | Separate components; composite awaiting validation | Note |

Show counts and the three separate shares. Refund evidence is package-level and cannot determine which Calendar visit or team caused the refund. The view has no date field, so use the 2026 snapshot scope. There is no defensible difficulty score, causal team ranking, or treatment success score.

## Weather context

Source: [dashboard_weather_monthly.sql](../dbt/models/gold/dashboard_weather_monthly.sql), built from [calendar_event_weather.sql](../dbt/models/calendar_event_weather.sql). One row represents `service_month × event_group`, where groups are `recorded_warranty_signal` and `other_scheduled_service_entry`.

Weather is Open-Meteo reanalysis at a roughly 9 km weather-grid scale, associated with rounded service-location candidates. It is not a sensor reading at the customer premise. Previous-day windows exclude the visit day. Dashboard means include only events with all previous 14 weather days available.

| Field | Meaning and unit | Use |
|---|---|---|
| `service_month` | Scheduled event month in 2026 | Date/month control |
| `event_group` | Warranty-signal or other scheduled-entry group | Two-series comparison |
| `scheduled_event_rows` | All entries in this month/group, including those without usable weather | Coverage denominator |
| `complete_prior_14d_weather_rows` | Entries with 14 preceding weather days available | Weather sample size/coverage numerator |
| `complete_weather_coverage_share` | Complete-window entries / all entries | Recalculate across months/groups |
| `avg_prior_3d_precipitation_mm` | Mean cumulative rainfall across previous 3 days | Millimetres |
| `avg_prior_7d_precipitation_mm` | Mean cumulative rainfall across previous 7 days | Millimetres |
| `avg_prior_14d_precipitation_mm` | Mean cumulative rainfall across previous 14 days | Millimetres |
| `avg_prior_7d_relative_humidity_pct` | Mean previous-7-day relative humidity | Percent on 0–100 scale |
| `avg_prior_7d_soil_moisture` | Mean previous-7-day top 0–7 cm soil moisture | Volumetric water fraction, m³/m³ |
| `weather_evidence` | Reanalysis association and causal limitation | Visible note |

Use monthly two-series charts to compare rainfall and humidity context, with a weather coverage table or cards beside them. Soil moisture can be a supplementary chart with its unit shown. Retain blank means when no complete windows exist.

Coverage across months = `SUM(complete_prior_14d_weather_rows) / SUM(scheduled_event_rows)`.

To combine monthly means, use a weighted mean. For example, create a row-level numerator `avg_prior_7d_precipitation_mm * complete_prior_14d_weather_rows`, then calculate `SUM(weighted_rain_numerator) / SUM(complete_prior_14d_weather_rows)`. Apply the same rule to the other mean fields. Verify the result in Gold; unweighted `AVG` of monthly means gives a small month the same influence as a large month. Cluster weather has property weighting and must not be merged with this event-weighted average.

No area, pest or Calendar field exists in this monthly weather view. Those filters cannot legitimately control these charts. No flooding, waterway-distance or temperature field is published here. Environmental variables used in the modelling experiment should not be presented as dashboard measures without a separate approved aggregate source.

Future scheduled visits may have no observed weather. A fresh daily reporting release does not establish that the weather cache reaches the same date: coverage remains essential. The published source-freshness view does not include weather-cache extent.

Management can discuss seasonal planning and investigate patterns where sample size and coverage are adequate. Comparisons are observational and can reflect geography, pest mix, package mix and recording practice. They do not demonstrate that rainfall or flooding caused pests, returns or treatment failure.

## Data quality

Source: [dashboard_data_quality.sql](../dbt/models/gold/dashboard_data_quality.sql), based on [recorded_activity_quality.sql](../dbt/models/gold/recorded_activity_quality.sql). One row is one `source_name × issue_code`. These are whole-source checks, not rows split by reporting month.

| Field | Meaning | Aggregation |
|---|---|---|
| `source_name` | Source being checked | Group/filter |
| `issue_code` | Specific handling/review category | Table row |
| `affected_rows` | Number of source records in this category | Use the specific issue count |
| `source_rows` | Total source-record denominator for this issue | Do not sum repeated denominators |
| `affected_share` | Affected rows / this source denominator | Display per issue |
| `reviewed_date` | Current Malaysia query date | Does not mean the original source was corrected that day |
| `denominator_evidence` | Issues can overlap | Visible note |

| Source | Issue | Meaning / stakeholder action |
|---|---|---|
| Sales | `excluded_disposition` | Source rows excluded by sale-disposition rules; distinguish intentional exclusions from sold packages |
| Sales | `undated_close` | No resolved close date; review before monthly comparison |
| Sales | `unparsed_or_blank_total` | Eligible sale lacks parsed value; correct source amount |
| Sales | `inferred_close_year` | Year recovered from sequence/timestamp evidence; keep inference visible |
| Payments | `undated_payment` | Payment date unavailable; review source |
| Payments | `text_date` | Date stored as text; handling category, not automatically an error |
| Payments | `future_date` | Payment date after current Malaysia date; verify its meaning |
| Payments | `unparsed_or_blank_amount` | Amount unavailable; review source |
| Payments | `combined_reference` | One payment entry references multiple packages; preserve combined amount once |
| Payments | `reference_needs_review` | Missing, unrecognized or repeated reference; investigate linking |
| Prospects | `undated_first_reply` | First-reply date unavailable; not assigned to a reporting month |
| Prospects | `acquisition_needs_review` | Acquisition label requires review |
| Prospects | `status_needs_review` | Status label requires review |

A single record can occur in several categories. Never sum all `affected_rows` into a unique bad-record total. `text_date`, `combined_reference` and deliberate exclusions do not automatically indicate invalid records. Present each category's count, denominator and interpretation. Calendar matching/location/weather coverage comes from the service measures; this quality view does not publish Calendar/geocode issue codes.

## Source freshness

Source: [dashboard_source_freshness.sql](../dbt/models/gold/dashboard_source_freshness.sql). One row represents a source snapshot included in the published reporting release.

| Field | Meaning | Use |
|---|---|---|
| `source_name` | Source label | Freshness table |
| `snapshot_table` | Immutable Bronze table used for that release | Technical provenance if needed |
| `extracted_at_utc` | Source extraction timestamp | Display time with timezone; MYT is UTC+8 |
| `release_run_id` | Validated release identifier | Release provenance |
| `hours_since_extraction` | Current whole-hour age of snapshot | MAX for oldest source age; never SUM |
| `freshness_evidence` | Publication and extraction interpretation | Note |

Published source rows cover b2b, sales, payments, payment date serials, payment links, warranty claims, commercial clients, refunds, recurring payments, Calendar and prospects. Stable Gold views are published after release checks. A failed refresh can leave the last successful snapshot visible, so management should inspect freshness before decisions.

Extraction time is not the time of the most recent sale, completed service, correction or model prediction. Missing extraction timestamps require review; they do not mean a source age of zero. A freshness table and oldest-source-age card provide source-backed attention items without inventing a business alert.

## Measures currently unavailable

The approved aggregate sources do not establish unique customer identity, completed treatments, technician effectiveness, capacity utilisation, confirmed reinfestation, treatment failure rate, causal environmental effects, live outbreak boundaries or a validated difficulty score. They also do not expose property histories or individual experimental risk scores. Use the recorded activity measures above to support management review, and retain the model's aggregate experimental evaluation on its separate page.
