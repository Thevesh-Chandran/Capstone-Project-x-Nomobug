-- Redacted diagnostics for unmatched Calendar service-candidate phone shapes.
-- Only length/prefix buckets are returned; phone values are never selected.
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
), parsed AS (
  SELECT
    REGEXP_EXTRACT(
      description_text,
      r'(?im)^[ \t*_]*(?:Phone[ \t]*(?:No\.?|Number)?|No\.?[ \t]*(?:Tel|Telefon|Fon)|Contact[ \t]*Number|H/P|Mobile[ \t]*No\.?)\s*[ \t*_]*:\s*([^\r\n<]+)'
    ) AS phone_raw
  FROM raw
), digits AS (
  SELECT
    REGEXP_REPLACE(phone_raw, r'\D', '') AS phone_digits
  FROM parsed
  WHERE phone_raw IS NOT NULL
)
SELECT
  LENGTH(phone_digits) AS digit_length,
  CASE
    WHEN STARTS_WITH(phone_digits, '60') THEN 'starts_60'
    WHEN STARTS_WITH(phone_digits, '0') THEN 'starts_0'
    WHEN STARTS_WITH(phone_digits, '1') THEN 'starts_1'
    ELSE 'other_prefix'
  END AS prefix_bucket,
  COUNT(*) AS event_count
FROM digits
GROUP BY 1, 2
ORDER BY 1, 2;
