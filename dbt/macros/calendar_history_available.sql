{% macro calendar_history_available(history_alias, anchor_alias) %}
-- A backdated entry created after the prediction did not exist as a predictor.
-- Unknown creation times stay excluded rather than being assumed available.
{{ history_alias }}.event_created_ts <= {{ anchor_alias }}.event_end_ts
{% endmacro %}
