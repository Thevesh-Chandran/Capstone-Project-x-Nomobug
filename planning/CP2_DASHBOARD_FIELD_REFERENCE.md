# Deployed dashboard field reference — 1 October 2026

Metadata-only schema read from the stable Gold views at 2026-09-30T16:22:30.167855+00:00. No customer records are reproduced here. Read the [build guide](CP2_DASHBOARD_BUILD_GUIDE.md), [finance/customer dictionary](CP2_METRIC_DICTIONARY.md), [operations dictionary](CP2_OPERATIONS_METRIC_DICTIONARY.md) and [model explanation](CP2_MODEL_EXPLAINED.md) for meanings, aggregation and limitations.

INTEGER/FLOAT/NUMERIC fields can contain counts, amounts, ratios or coordinates; choose aggregation by meaning, not by type alone. STRING fields are labels/metadata, DATE fields are reporting dates, TIMESTAMP fields record time, and BOOLEAN fields are yes/no. BigQuery mode NULLABLE means missing values are permitted.

## gold.sales_monthly_recorded

| Exact field | BigQuery type | Mode |
|---|---|---|
| `snapshot_table` | STRING | NULLABLE |
| `closed_month` | DATE | NULLABLE |
| `package_rows` | INTEGER | NULLABLE |
| `countable_package_rows` | INTEGER | NULLABLE |
| `recorded_package_face_value_rm` | NUMERIC | NULLABLE |
| `unparsed_or_blank_total_rows` | INTEGER | NULLABLE |
| `excluded_disposition_rows` | INTEGER | NULLABLE |
| `undated_rows` | INTEGER | NULLABLE |
| `future_dated_rows` | INTEGER | NULLABLE |
| `inferred_year_rows` | INTEGER | NULLABLE |

## gold.payments_monthly_recorded

| Exact field | BigQuery type | Mode |
|---|---|---|
| `snapshot_table` | STRING | NULLABLE |
| `payment_month` | DATE | NULLABLE |
| `payment_rows` | INTEGER | NULLABLE |
| `dated_nonfuture_rows` | INTEGER | NULLABLE |
| `recorded_payment_entry_amount_rm` | NUMERIC | NULLABLE |
| `unparsed_or_blank_amount_rows` | INTEGER | NULLABLE |
| `text_date_review_rows` | INTEGER | NULLABLE |
| `undated_rows` | INTEGER | NULLABLE |
| `future_dated_rows` | INTEGER | NULLABLE |
| `combined_reference_rows` | INTEGER | NULLABLE |
| `reference_review_rows` | INTEGER | NULLABLE |

## gold.prospect_reply_monthly_recorded

| Exact field | BigQuery type | Mode |
|---|---|---|
| `snapshot_id` | STRING | NULLABLE |
| `snapshot_extracted_at` | TIMESTAMP | NULLABLE |
| `first_reply_month` | DATE | NULLABLE |
| `prospect_candidate_rows` | INTEGER | NULLABLE |
| `recorded_open_rows` | INTEGER | NULLABLE |
| `recorded_closed_rows` | INTEGER | NULLABLE |
| `exact_won_remark_rows` | INTEGER | NULLABLE |
| `undated_first_reply_rows` | INTEGER | NULLABLE |
| `future_first_reply_rows` | INTEGER | NULLABLE |
| `acquisition_review_rows` | INTEGER | NULLABLE |

## gold.dashboard_service_monthly

| Exact field | BigQuery type | Mode |
|---|---|---|
| `service_month` | DATE | NULLABLE |
| `scheduled_service_event_rows` | INTEGER | NULLABLE |
| `normal_package_service_event_rows` | INTEGER | NULLABLE |
| `warranty_claim_event_rows` | INTEGER | NULLABLE |
| `generic_complimentary_event_rows` | INTEGER | NULLABLE |
| `matched_sales_event_rows` | INTEGER | NULLABLE |
| `unmatched_sales_event_rows` | INTEGER | NULLABLE |
| `heatmap_eligible_event_rows` | INTEGER | NULLABLE |
| `heatmap_eligible_warranty_claim_rows` | INTEGER | NULLABLE |
| `warranty_claims_with_complete_prior_14d_weather` | INTEGER | NULLABLE |
| `warranty_claim_event_share` | FLOAT | NULLABLE |
| `heatmap_warranty_claim_share` | FLOAT | NULLABLE |
| `denominator_evidence` | STRING | NULLABLE |

## gold.dashboard_scheduling_capacity

| Exact field | BigQuery type | Mode |
|---|---|---|
| `service_date` | DATE | NULLABLE |
| `calendar_name` | STRING | NULLABLE |
| `day_of_week_number` | INTEGER | NULLABLE |
| `scheduled_event_rows` | INTEGER | NULLABLE |
| `normal_package_event_rows` | INTEGER | NULLABLE |
| `warranty_claim_event_rows` | INTEGER | NULLABLE |
| `generic_complimentary_event_rows` | INTEGER | NULLABLE |
| `extra_visit_signal_rows` | INTEGER | NULLABLE |
| `matched_sales_event_rows` | INTEGER | NULLABLE |
| `unmatched_sales_event_rows` | INTEGER | NULLABLE |
| `ambiguous_sales_event_rows` | INTEGER | NULLABLE |
| `denominator_evidence` | STRING | NULLABLE |

## gold.dashboard_recurrence_monthly

| Exact field | BigQuery type | Mode |
|---|---|---|
| `service_month` | DATE | NULLABLE |
| `recurrence_bucket` | STRING | NULLABLE |
| `recurrence_reason` | STRING | NULLABLE |
| `recorded_warranty_signal_rows` | INTEGER | NULLABLE |
| `property_text_available_rows` | INTEGER | NULLABLE |
| `property_review_rows` | INTEGER | NULLABLE |
| `denominator_evidence` | STRING | NULLABLE |

## gold.dashboard_spatial_area

| Exact field | BigQuery type | Mode |
|---|---|---|
| `area_cell` | STRING | NULLABLE |
| `area_centroid_latitude` | FLOAT | NULLABLE |
| `area_centroid_longitude` | FLOAT | NULLABLE |
| `scheduled_service_event_rows` | INTEGER | NULLABLE |
| `matched_sales_records` | INTEGER | NULLABLE |
| `repeat_signal_event_rows` | INTEGER | NULLABLE |
| `warranty_label_event_rows` | INTEGER | NULLABLE |
| `over_sequence_event_rows` | INTEGER | NULLABLE |
| `repeat_signal_share` | FLOAT | NULLABLE |
| `map_grain_evidence` | STRING | NULLABLE |
| `denominator_evidence` | STRING | NULLABLE |

## gold.dashboard_spatial_cluster_summary

| Exact field | BigQuery type | Mode |
|---|---|---|
| `radius_km` | INTEGER | NULLABLE |
| `cluster_id` | INTEGER | NULLABLE |
| `cluster_centroid_latitude` | FLOAT | NULLABLE |
| `cluster_centroid_longitude` | FLOAT | NULLABLE |
| `distinct_service_properties` | INTEGER | NULLABLE |
| `recorded_warranty_signal_rows` | INTEGER | NULLABLE |
| `property_level_sales_package_rows` | INTEGER | NULLABLE |
| `complete_prior_14d_weather_rows` | INTEGER | NULLABLE |
| `avg_prior_7d_precipitation_mm` | FLOAT | NULLABLE |
| `avg_prior_7d_relative_humidity_pct` | FLOAT | NULLABLE |
| `avg_prior_7d_soil_moisture` | FLOAT | NULLABLE |
| `cluster_evidence` | STRING | NULLABLE |

## gold.dashboard_weather_monthly

| Exact field | BigQuery type | Mode |
|---|---|---|
| `service_month` | DATE | NULLABLE |
| `event_group` | STRING | NULLABLE |
| `scheduled_event_rows` | INTEGER | NULLABLE |
| `complete_prior_14d_weather_rows` | INTEGER | NULLABLE |
| `complete_weather_coverage_share` | FLOAT | NULLABLE |
| `avg_prior_3d_precipitation_mm` | FLOAT | NULLABLE |
| `avg_prior_7d_precipitation_mm` | FLOAT | NULLABLE |
| `avg_prior_14d_precipitation_mm` | FLOAT | NULLABLE |
| `avg_prior_7d_relative_humidity_pct` | FLOAT | NULLABLE |
| `avg_prior_7d_soil_moisture` | FLOAT | NULLABLE |
| `weather_evidence` | STRING | NULLABLE |

## gold.dashboard_package_fit_matrix

| Exact field | BigQuery type | Mode |
|---|---|---|
| `pest_type` | STRING | NULLABLE |
| `package_type` | STRING | NULLABLE |
| `contract_type` | STRING | NULLABLE |
| `package_rows` | INTEGER | NULLABLE |
| `packages_with_payment_evidence` | INTEGER | NULLABLE |
| `recorded_package_face_value_rm` | NUMERIC | NULLABLE |
| `linked_payment_entry_rows` | INTEGER | NULLABLE |
| `scheduled_event_rows` | INTEGER | NULLABLE |
| `warranty_claim_event_rows` | INTEGER | NULLABLE |
| `generic_complimentary_event_rows` | INTEGER | NULLABLE |
| `payment_evidence_rate` | FLOAT | NULLABLE |
| `warranty_event_share` | FLOAT | NULLABLE |
| `denominator_evidence` | STRING | NULLABLE |

## gold.dashboard_payment_link_monthly

| Exact field | BigQuery type | Mode |
|---|---|---|
| `payment_link_month` | DATE | NULLABLE |
| `payment_link_source_rows` | INTEGER | NULLABLE |
| `recorded_won_rows` | INTEGER | NULLABLE |
| `missing_status_rows` | INTEGER | NULLABLE |
| `date_review_rows` | INTEGER | NULLABLE |
| `outcome_text_rows` | INTEGER | NULLABLE |
| `denominator_evidence` | STRING | NULLABLE |

## gold.dashboard_refund_monthly

| Exact field | BigQuery type | Mode |
|---|---|---|
| `refund_month` | DATE | NULLABLE |
| `refund_source_rows` | INTEGER | NULLABLE |
| `linked_refund_rows` | INTEGER | NULLABLE |
| `unmatched_refund_rows` | INTEGER | NULLABLE |
| `recorded_complete_rows` | INTEGER | NULLABLE |
| `status_review_rows` | INTEGER | NULLABLE |
| `amount_review_rows` | INTEGER | NULLABLE |
| `date_review_rows` | INTEGER | NULLABLE |
| `recorded_refund_amount_rm` | NUMERIC | NULLABLE |
| `denominator_evidence` | STRING | NULLABLE |

## gold.dashboard_warranty_package_metrics

Package-grain internal context. The aggregate management build does not connect this source or expose sale IDs.

| Exact field | BigQuery type | Mode |
|---|---|---|
| `sales_record_id` | STRING | NULLABLE |
| `closed_date` | DATE | NULLABLE |
| `package_sessions_recorded` | INTEGER | NULLABLE |
| `package_type_raw` | STRING | NULLABLE |
| `contract_type_raw` | STRING | NULLABLE |
| `sale_disposition` | STRING | NULLABLE |
| `scheduled_service_event_rows` | INTEGER | NULLABLE |
| `normal_package_service_event_rows` | INTEGER | NULLABLE |
| `warranty_claim_event_rows` | INTEGER | NULLABLE |
| `generic_complimentary_event_rows` | INTEGER | NULLABLE |
| `heatmap_eligible_event_rows` | INTEGER | NULLABLE |
| `heatmap_eligible_warranty_claim_rows` | INTEGER | NULLABLE |
| `warranty_claims_with_complete_prior_14d_weather` | INTEGER | NULLABLE |
| `first_calendar_service_date` | DATE | NULLABLE |
| `last_calendar_service_date` | DATE | NULLABLE |
| `has_warranty_claim_signal` | BOOLEAN | NULLABLE |
| `warranty_claim_event_share` | FLOAT | NULLABLE |
| `heatmap_warranty_claim_share` | FLOAT | NULLABLE |
| `denominator_evidence` | STRING | NULLABLE |

## gold.dashboard_treatment_difficulty

| Exact field | BigQuery type | Mode |
|---|---|---|
| `area_cell` | STRING | NULLABLE |
| `calendar_name` | STRING | NULLABLE |
| `pest_type` | STRING | NULLABLE |
| `package_type` | STRING | NULLABLE |
| `scheduled_event_rows` | INTEGER | NULLABLE |
| `matched_sales_records` | INTEGER | NULLABLE |
| `warranty_claim_event_rows` | INTEGER | NULLABLE |
| `extra_visit_signal_rows` | INTEGER | NULLABLE |
| `linked_refund_event_rows` | INTEGER | NULLABLE |
| `warranty_signal_share` | FLOAT | NULLABLE |
| `extra_visit_signal_share` | FLOAT | NULLABLE |
| `linked_refund_signal_share` | FLOAT | NULLABLE |
| `treatment_difficulty_proxy_0_100` | FLOAT | NULLABLE |
| `sufficient_volume_for_comparison` | BOOLEAN | NULLABLE |
| `score_evidence` | STRING | NULLABLE |

## gold.dashboard_source_freshness

| Exact field | BigQuery type | Mode |
|---|---|---|
| `source_name` | STRING | NULLABLE |
| `snapshot_table` | STRING | NULLABLE |
| `extracted_at_utc` | TIMESTAMP | NULLABLE |
| `release_run_id` | STRING | NULLABLE |
| `hours_since_extraction` | INTEGER | NULLABLE |
| `freshness_evidence` | STRING | NULLABLE |

## gold.dashboard_data_quality

| Exact field | BigQuery type | Mode |
|---|---|---|
| `source_name` | STRING | NULLABLE |
| `issue_code` | STRING | NULLABLE |
| `affected_rows` | INTEGER | NULLABLE |
| `source_rows` | INTEGER | NULLABLE |
| `affected_share` | FLOAT | NULLABLE |
| `reviewed_date` | DATE | NULLABLE |
| `denominator_evidence` | STRING | NULLABLE |

## gold.dashboard_ml_evaluation

| Exact field | BigQuery type | Mode |
|---|---|---|
| `run_utc` | TIMESTAMP | NULLABLE |
| `model_name` | STRING | NULLABLE |
| `model_role` | STRING | NULLABLE |
| `metric_name` | STRING | NULLABLE |
| `metric_value` | FLOAT | NULLABLE |
| `training_rows` | INTEGER | NULLABLE |
| `holdout_rows` | INTEGER | NULLABLE |
| `training_positive_rows` | INTEGER | NULLABLE |
| `holdout_positive_rows` | INTEGER | NULLABLE |
| `target_definition` | STRING | NULLABLE |
| `prediction_time_definition` | STRING | NULLABLE |
| `label_evidence` | STRING | NULLABLE |
| `split_definition` | STRING | NULLABLE |
| `feature_set_definition` | STRING | NULLABLE |
| `evaluation_cohort` | STRING | NULLABLE |
| `experiment_status` | STRING | NULLABLE |

