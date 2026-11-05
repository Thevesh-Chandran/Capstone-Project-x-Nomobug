-- Redacted test of a safer phone candidate extractor.
-- It checks whether unmatched service candidates have a mobile number embedded
-- in a noisy phone field; no phone values are returned.
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
    AND m.phone_present
), calendar_keys AS (
  SELECT
    calendar_event_row,
    CASE
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(phone_raw, r'\D', ''), r'60(1\d{8,9})')
        THEN CONCAT('0', REGEXP_EXTRACT(REGEXP_REPLACE(phone_raw, r'\D', ''), r'60(1\d{8,9})'))
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(phone_raw, r'\D', ''), r'(01\d{8,9})')
        THEN REGEXP_EXTRACT(REGEXP_REPLACE(phone_raw, r'\D', ''), r'(01\d{8,9})')
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(phone_raw, r'\D', ''), r'(1\d{8,9})')
        THEN CONCAT('0', REGEXP_EXTRACT(REGEXP_REPLACE(phone_raw, r'\D', ''), r'(1\d{8,9})'))
      ELSE REGEXP_REPLACE(phone_raw, r'\D', '')
    END AS phone_key
  FROM (
    SELECT
      calendar_event_row,
      REGEXP_EXTRACT(
        description_text,
        r'(?im)^[ \t*_]*(?:Phone[ \t]*(?:No\.?|Number)?|No\.?[ \t]*(?:Tel|Telefon|Fon)|Contact[ \t]*Number|H/P|Mobile[ \t]*No\.?)\s*[ \t*_]*:\s*([^\r\n<]+)'
      ) AS phone_raw
    FROM raw
  )
), sales_keys AS (
  SELECT
    TRIM(source_column_007) AS sales_record_id,
    CASE
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(source_column_010, r'\D', ''), r'60(1\d{8,9})')
        THEN CONCAT('0', REGEXP_EXTRACT(REGEXP_REPLACE(source_column_010, r'\D', ''), r'60(1\d{8,9})'))
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(source_column_010, r'\D', ''), r'(01\d{8,9})')
        THEN REGEXP_EXTRACT(REGEXP_REPLACE(source_column_010, r'\D', ''), r'(01\d{8,9})')
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(source_column_010, r'\D', ''), r'(1\d{8,9})')
        THEN CONCAT('0', REGEXP_EXTRACT(REGEXP_REPLACE(source_column_010, r'\D', ''), r'(1\d{8,9})'))
      ELSE REGEXP_REPLACE(source_column_010, r'\D', '')
    END AS phone_key
  FROM `profound-keel-500007-s4.bronze.sales_6d1d3d3155b4ca3f57df14237b344cc2be163516d7b22f4f8ab1a305de80c2b8`
  WHERE TRIM(source_column_007) != ''
), per_event AS (
  SELECT
    c.calendar_event_row,
    COUNT(DISTINCT s.sales_record_id) AS candidate_sales_matches
  FROM calendar_keys AS c
  LEFT JOIN sales_keys AS s
    ON c.phone_key != '' AND c.phone_key = s.phone_key
  GROUP BY 1
)
SELECT
  CASE
    WHEN candidate_sales_matches = 0 THEN 'still_no_sales_phone_match'
    WHEN candidate_sales_matches = 1 THEN 'one_candidate_sales_match'
    ELSE 'multiple_candidate_sales_matches'
  END AS diagnostic_result,
  COUNT(*) AS event_count
FROM per_event
GROUP BY 1
ORDER BY 1;
