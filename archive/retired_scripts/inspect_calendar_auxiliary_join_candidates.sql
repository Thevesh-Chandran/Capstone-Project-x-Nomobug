-- Redacted check for unmatched Calendar service candidates against supporting
-- operational sources. Only match-count buckets are returned.
WITH raw AS (
  SELECT
    m.calendar_event_row,
    e.event_date_local,
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
  WHERE m.matching_scope = 'service_candidate'
    AND m.match_status = 'unmatched'
), calendar_keys AS (
  SELECT
    calendar_event_row,
    event_date_local,
    CASE
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(phone_raw, r'\D', ''), r'60(1\d{8,9})')
        THEN CONCAT('0', REGEXP_EXTRACT(REGEXP_REPLACE(phone_raw, r'\D', ''), r'60(1\d{8,9})'))
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(phone_raw, r'\D', ''), r'(01\d{8,9})')
        THEN REGEXP_EXTRACT(REGEXP_REPLACE(phone_raw, r'\D', ''), r'(01\d{8,9})')
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(phone_raw, r'\D', ''), r'(1\d{8,9})')
        THEN CONCAT('0', REGEXP_EXTRACT(REGEXP_REPLACE(phone_raw, r'\D', ''), r'(1\d{8,9})'))
      ELSE REGEXP_REPLACE(phone_raw, r'\D', '')
    END AS phone_key,
    LOWER(TRIM(email_raw)) AS email_key
  FROM (
    SELECT
      calendar_event_row,
      event_date_local,
      REGEXP_EXTRACT(
        description_text,
        r'(?im)^[ \t*_]*(?:Phone[ \t]*(?:No\.?|Number)?|No\.?[ \t]*(?:Tel|Telefon|Fon)|Contact[ \t]*Number|H/P|Mobile[ \t]*No\.?)\s*[ \t*_]*:\s*([^\r\n<]+)'
      ) AS phone_raw,
      REGEXP_EXTRACT(
        description_text,
        r'(?im)^[ \t*_]*(?:Emel|Email|E-Mail|Valid\s+Emel)[ \t*_]*:\s*([^\r\n<]+)'
      ) AS email_raw
    FROM raw
  )
), supporting_keys AS (
  SELECT
    'b2b' AS source_name,
    CAST(source_sheet_row AS STRING) AS source_row,
    CASE
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(source_column_003, r'\D', ''), r'60(1\d{8,9})')
        THEN CONCAT('0', REGEXP_EXTRACT(REGEXP_REPLACE(source_column_003, r'\D', ''), r'60(1\d{8,9})'))
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(source_column_003, r'\D', ''), r'(01\d{8,9})')
        THEN REGEXP_EXTRACT(REGEXP_REPLACE(source_column_003, r'\D', ''), r'(01\d{8,9})')
      ELSE REGEXP_REPLACE(source_column_003, r'\D', '')
    END AS phone_key,
    '' AS email_key
  FROM `profound-keel-500007-s4.bronze.b2b_follow_up_9108505ec89b8d23513fae1a2aba7e0d63466b7ceb1dc1ea99b451167047231d`
  UNION ALL
  SELECT
    'commercial_clients', CAST(source_sheet_row AS STRING),
    CASE
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(source_column_009, r'\D', ''), r'60(1\d{8,9})')
        THEN CONCAT('0', REGEXP_EXTRACT(REGEXP_REPLACE(source_column_009, r'\D', ''), r'60(1\d{8,9})'))
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(source_column_009, r'\D', ''), r'(01\d{8,9})')
        THEN REGEXP_EXTRACT(REGEXP_REPLACE(source_column_009, r'\D', ''), r'(01\d{8,9})')
      ELSE REGEXP_REPLACE(source_column_009, r'\D', '')
    END,
    LOWER(TRIM(source_column_011))
  FROM `profound-keel-500007-s4.bronze.commercial_clients_60e12ac95a426cddd7fdc03c2de5e92337feb525b559260617147e11d58576fd`
  UNION ALL
  SELECT
    'recurring_payments', CAST(source_sheet_row AS STRING),
    CASE
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(source_column_008, r'\D', ''), r'60(1\d{8,9})')
        THEN CONCAT('0', REGEXP_EXTRACT(REGEXP_REPLACE(source_column_008, r'\D', ''), r'60(1\d{8,9})'))
      WHEN REGEXP_CONTAINS(REGEXP_REPLACE(source_column_008, r'\D', ''), r'(01\d{8,9})')
        THEN REGEXP_EXTRACT(REGEXP_REPLACE(source_column_008, r'\D', ''), r'(01\d{8,9})')
      ELSE REGEXP_REPLACE(source_column_008, r'\D', '')
    END,
    LOWER(TRIM(source_column_009))
  FROM `profound-keel-500007-s4.bronze.recurring_payments_5f68eb4fd2c39e1913717dea880bbde75b0cc29c429adc14009c9c0f0cac03c2`
), per_event AS (
  SELECT
    c.calendar_event_row,
    COUNT(DISTINCT IF(s.source_name = 'b2b' AND c.phone_key != '' AND c.phone_key = s.phone_key, s.source_row, NULL)) AS b2b_matches,
    COUNT(DISTINCT IF(s.source_name = 'commercial_clients' AND ((c.phone_key != '' AND c.phone_key = s.phone_key) OR (c.email_key != '' AND STRPOS(c.email_key, '@') > 0 AND c.email_key = s.email_key)), s.source_row, NULL)) AS commercial_matches,
    COUNT(DISTINCT IF(s.source_name = 'recurring_payments' AND ((c.phone_key != '' AND c.phone_key = s.phone_key) OR (c.email_key != '' AND STRPOS(c.email_key, '@') > 0 AND c.email_key = s.email_key)), s.source_row, NULL)) AS recurring_matches
  FROM calendar_keys AS c
  LEFT JOIN supporting_keys AS s
    ON (c.phone_key != '' AND c.phone_key = s.phone_key)
    OR (c.email_key != '' AND STRPOS(c.email_key, '@') > 0 AND c.email_key = s.email_key)
  GROUP BY 1
)
SELECT
  CASE
    WHEN EXTRACT(YEAR FROM c.event_date_local) = 2026 THEN '2026'
    ELSE 'pre_2026'
  END AS calendar_period,
  COUNT(*) AS unmatched_service_events,
  COUNTIF(p.b2b_matches > 0) AS b2b_candidate_events,
  COUNTIF(p.commercial_matches > 0) AS commercial_candidate_events,
  COUNTIF(p.recurring_matches > 0) AS recurring_candidate_events
FROM per_event AS p
JOIN calendar_keys AS c USING (calendar_event_row)
GROUP BY 1
ORDER BY 1;
