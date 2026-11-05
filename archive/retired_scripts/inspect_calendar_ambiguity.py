"""Read-only terminal summary of ambiguous 2026 Calendar-to-Sales matches."""

from google.cloud import bigquery

client = bigquery.Client(project="profound-keel-500007-s4")

sql = """
WITH ambiguous AS (
  SELECT calendar_event_row, calendar_name, event_date_local,
    CASE
      WHEN invoice_match_count > 1 THEN 'shared_invoice'
      WHEN phone_match_count > 1 THEN 'shared_phone'
      WHEN email_match_count > 1 THEN 'shared_email'
      WHEN address_match_count > 1 THEN 'shared_address'
      ELSE 'other_ambiguity'
    END AS reason,
    sales_match_count
  FROM `profound-keel-500007-s4.silver.calendar_event_matches`
  WHERE service_candidate
    AND event_date_local >= '2026-01-01'
    AND event_date_local < '2027-01-01'
    AND match_status = 'ambiguous_sales'
)
SELECT reason, COUNT(*) AS events,
  ARRAY_AGG(STRUCT(a.calendar_event_row, a.event_date_local,
                   c.summary, a.sales_match_count)
            ORDER BY a.event_date_local, a.calendar_event_row LIMIT 3) AS examples
FROM ambiguous a
JOIN `profound-keel-500007-s4.bronze.calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66` c
  USING (calendar_event_row)
GROUP BY reason
ORDER BY events DESC
"""

config = bigquery.QueryJobConfig(maximum_bytes_billed=104857600)
dry_run = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
estimate = client.query(sql, location="asia-southeast1", job_config=dry_run)
print(f"Estimated query bytes: {estimate.total_bytes_processed:,}")

if estimate.total_bytes_processed > 104857600:
    raise SystemExit("Stopped: estimated scan exceeds the 100 MiB safety limit.")

try:
    rows = client.query(sql, location="asia-southeast1", job_config=config).result()
    for row in rows:
        print(f"{row.reason}: {row.events} events")
        for example in row.examples:
            print(f"  row {example['calendar_event_row']}, {example['event_date_local']}, "
                  f"{example['summary']}, {example['sales_match_count']} Sales candidates")
except Exception as exc:
    if "Custom quota exceeded" in str(exc):
        raise SystemExit("Daily BigQuery query quota reached. No limit changed; retry after reset.") from None
    raise
finally:
    client.close()
