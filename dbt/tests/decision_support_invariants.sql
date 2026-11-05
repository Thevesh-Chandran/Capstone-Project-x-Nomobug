-- Return rows only for violated aggregate contracts.
select 'historical_counts' as failure from {{ ref('dashboard_model_review') }}
where services != 100 or positive_windows != 5 or reviews != 20
   or callbacks_found + callbacks_missed != positive_windows
   or callbacks_found + reviews_without_callback != reviews
   or abs(callback_capture - safe_divide(callbacks_found, positive_windows)) > 1e-10
union all
select 'development_counts' from {{ ref('dashboard_followup_baselines') }}
where callbacks_found < 0 or callbacks_missed < 0 or reviews_without_callback < 0
   or abs(callbacks_found + callbacks_missed - positive_windows) > 1e-8
   or abs(callbacks_found + reviews_without_callback - reviews) > 1e-8
union all
select 'unequal_review_budget' from {{ ref('dashboard_followup_baselines') }}
group by fold having count(*) != 3 or min(reviews) != max(reviews)
   or min(services) != max(services) or min(positive_windows) != max(positive_windows)
union all
select 'invalid_feature_comparison' from {{ ref('dashboard_feature_comparison') }}
where mean_average_precision not between 0 and 1 or mean_callback_capture not between 0 and 1
   or validation_folds != 3 or review_fraction != 0.2
union all
select 'invalid_attention' from {{ ref('dashboard_attention') }}
where item_count < 0 or amount_rm < 0 or action_date < as_of_date
   or (category in ('Payment reminders', 'Upcoming visits') and action_date >= date_add(as_of_date, interval 7 day))
