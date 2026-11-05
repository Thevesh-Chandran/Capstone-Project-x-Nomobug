-- Redacted test of punctuation-insensitive invoice matching.
-- This estimates whether unmatched invoice-bearing service events would match
-- Sales after removing punctuation; no invoice values are returned.
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
    AND m.invoice_present
), calendar_keys AS (
  SELECT
    calendar_event_row,
    REGEXP_REPLACE(
      UPPER(REGEXP_EXTRACT(
        description_text,
        r'(?im)^[ \t*_]*(?:Invoice(?:\s*ID)?|INV)[ \t*_]*:\s*([^\r\n<]+)'
      )),
      r'[^A-Z0-9]',
      ''
    ) AS invoice_key
  FROM raw
), sales_keys AS (
  SELECT
    TRIM(source_column_007) AS sales_record_id,
    REGEXP_REPLACE(UPPER(source_column_030), r'[^A-Z0-9]', '') AS invoice_a_key,
    REGEXP_REPLACE(UPPER(source_column_032), r'[^A-Z0-9]', '') AS invoice_b_key
  FROM `profound-keel-500007-s4.bronze.sales_6d1d3d3155b4ca3f57df14237b344cc2be163516d7b22f4f8ab1a305de80c2b8`
  WHERE TRIM(source_column_007) != ''
), per_event AS (
  SELECT
    c.calendar_event_row,
    COUNT(DISTINCT s.sales_record_id) AS clean_invoice_sales_matches
  FROM calendar_keys AS c
  LEFT JOIN sales_keys AS s
    ON c.invoice_key != ''
   AND (
     (s.invoice_a_key != '' AND (c.invoice_key = s.invoice_a_key OR STRPOS(c.invoice_key, s.invoice_a_key) > 0))
     OR (s.invoice_b_key != '' AND (c.invoice_key = s.invoice_b_key OR STRPOS(c.invoice_key, s.invoice_b_key) > 0))
   )
  GROUP BY 1
)
SELECT
  CASE
    WHEN clean_invoice_sales_matches > 0 THEN 'would_match_after_cleaning'
    ELSE 'still_no_sales_invoice_match'
  END AS diagnostic_result,
  COUNT(*) AS event_count
FROM per_event
GROUP BY 1
ORDER BY 1;
