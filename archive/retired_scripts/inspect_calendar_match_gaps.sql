-- Redacted diagnostics for unmatched Calendar service candidates.
-- This returns field-label counts only; it does not select description values.
WITH unmatched_service AS (
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
), labels AS (
  SELECT
    REGEXP_EXTRACT(line, r'(?i)^\s*([^:]{1,50}):') AS label
  FROM unmatched_service,
  UNNEST(SPLIT(description_text, CHR(10))) AS line
)
SELECT
  UPPER(TRIM(label)) AS label,
  COUNT(*) AS line_count
FROM labels
WHERE label IS NOT NULL
GROUP BY 1
ORDER BY line_count DESC
LIMIT 50;
