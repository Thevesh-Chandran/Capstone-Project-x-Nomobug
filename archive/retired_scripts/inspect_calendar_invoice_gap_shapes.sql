-- Redacted diagnostics for unmatched Calendar service-candidate invoice shapes.
-- Only normalized length/prefix buckets are returned; invoice values are never selected.
WITH raw AS (
  SELECT
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
    AND m.invoice_present
), parsed AS (
  SELECT
    REGEXP_EXTRACT(
      description_text,
      r'(?im)^[ \t*_]*(?:Invoice(?:\s*ID)?|INV)[ \t*_]*:\s*([^\r\n<]+)'
    ) AS invoice_raw
  FROM raw
), keys AS (
  SELECT REGEXP_REPLACE(UPPER(invoice_raw), r'[^A-Z0-9]', '') AS invoice_key
  FROM parsed
  WHERE invoice_raw IS NOT NULL
)
SELECT
  LENGTH(invoice_key) AS normalized_length,
  SUBSTR(invoice_key, 1, 8) AS prefix_bucket,
  COUNT(*) AS event_count
FROM keys
GROUP BY 1, 2
ORDER BY event_count DESC
LIMIT 50;
