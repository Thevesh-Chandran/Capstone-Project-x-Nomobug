-- Redacted diagnostic for name containment candidates on unmatched service events.
-- It reports only candidate-count buckets; no names are returned.
WITH calendar_keys AS (
  SELECT
    m.calendar_event_row,
    UPPER(REGEXP_REPLACE(
      REGEXP_EXTRACT(UPPER(COALESCE(b.summary, '')), r'\b\d{1,2}\s*/\s*\d{1,2}\s+(.+)$'),
      r'[^A-Z0-9]',
      ''
    )) AS title_name_key
  FROM `profound-keel-500007-s4.silver.calendar_event_matches` AS m
  JOIN `profound-keel-500007-s4.silver.calendar_events` AS e
    USING (calendar_event_row)
  JOIN `profound-keel-500007-s4.bronze.calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66` AS b
    USING (calendar_event_row)
  WHERE m.matching_scope = 'service_candidate'
    AND m.match_status = 'unmatched'
), sales_keys AS (
  SELECT
    TRIM(source_column_007) AS sales_record_id,
    UPPER(REGEXP_REPLACE(source_column_009, r'[^A-Z0-9]', '')) AS name_key
  FROM `profound-keel-500007-s4.bronze.sales_6d1d3d3155b4ca3f57df14237b344cc2be163516d7b22f4f8ab1a305de80c2b8`
  WHERE TRIM(source_column_007) != ''
    AND TRIM(source_column_009) != ''
), per_event AS (
  SELECT
    c.calendar_event_row,
    COUNT(DISTINCT s.sales_record_id) AS containment_sales_matches
  FROM calendar_keys AS c
  LEFT JOIN sales_keys AS s
    ON c.title_name_key != ''
   AND s.name_key != ''
   AND (STRPOS(c.title_name_key, s.name_key) > 0 OR STRPOS(s.name_key, c.title_name_key) > 0)
  GROUP BY 1
)
SELECT
  CASE
    WHEN containment_sales_matches = 0 THEN 'no_containment_candidate'
    WHEN containment_sales_matches = 1 THEN 'one_containment_candidate'
    ELSE 'multiple_containment_candidates'
  END AS diagnostic_result,
  COUNT(*) AS event_count
FROM per_event
GROUP BY 1
ORDER BY 1;
