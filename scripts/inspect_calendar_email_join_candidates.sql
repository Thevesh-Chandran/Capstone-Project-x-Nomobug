-- Redacted test of exact email matching for unmatched service candidates.
-- Only candidate-count buckets are returned; email values are never selected.
WITH raw AS (
  SELECT
    m.calendar_event_row,
    REGEXP_REPLACE(
      REGEXP_REPLACE(COALESCE(b.description, ''), r'(?i)<br\s*/?>', CHR(10)),
      r'<[^>]+>',
      ''
    ) AS description_text
  FROM `profound-keel-500007-s4.silver.calendar_event_matches` AS m
  JOIN `profound-keel-500007-s4.silver.calendar_events` AS e
    USING (calendar_event_row)
  JOIN `profound-keel-500007-s4.bronze.calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66` AS b
    USING (calendar_event_row)
  WHERE m.match_status = 'unmatched'
    AND e.service_candidate
    AND m.email_present
), calendar_keys AS (
  SELECT
    calendar_event_row,
    LOWER(TRIM(REGEXP_EXTRACT(
      description_text,
      r'(?im)^[ \t*_]*(?:Emel|Email|E-Mail|Valid\s+Emel)[ \t*_]*:\s*([^\r\n<]+)'
    ))) AS email_key
  FROM raw
), sales_keys AS (
  SELECT
    TRIM(source_column_007) AS sales_record_id,
    LOWER(TRIM(source_column_012)) AS email_key
  FROM `profound-keel-500007-s4.bronze.sales_6d1d3d3155b4ca3f57df14237b344cc2be163516d7b22f4f8ab1a305de80c2b8`
  WHERE TRIM(source_column_007) != ''
    AND TRIM(source_column_012) != ''
), per_event AS (
  SELECT
    c.calendar_event_row,
    COUNT(DISTINCT s.sales_record_id) AS email_sales_matches
  FROM calendar_keys AS c
  LEFT JOIN sales_keys AS s
    ON c.email_key != '' AND c.email_key = s.email_key
  GROUP BY 1
)
SELECT
  CASE
    WHEN email_sales_matches = 0 THEN 'no_sales_email_match'
    WHEN email_sales_matches = 1 THEN 'one_candidate_sales_match'
    ELSE 'multiple_candidate_sales_matches'
  END AS diagnostic_result,
  COUNT(*) AS event_count
FROM per_event
GROUP BY 1
ORDER BY 1;
