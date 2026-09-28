"""Print every ambiguous 2026 Calendar service event in the terminal."""

from google.cloud import bigquery

client = bigquery.Client(project="profound-keel-500007-s4")

sql = """
SELECT m.event_date_local, c.summary, m.calendar_event_row,
       m.sales_match_count,
       CASE
         WHEN m.invoice_match_count > 1 THEN 'shared invoice'
         WHEN m.phone_match_count > 1 THEN 'shared phone'
         WHEN m.email_match_count > 1 THEN 'shared email'
         WHEN m.address_match_count > 1 THEN 'shared address'
         ELSE 'other'
       END AS reason
FROM `profound-keel-500007-s4.silver.calendar_event_matches` m
JOIN `profound-keel-500007-s4.bronze.calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66` c
  USING (calendar_event_row)
WHERE m.service_candidate
  AND m.event_date_local >= '2026-01-01'
  AND m.event_date_local < '2027-01-01'
  AND m.match_status = 'ambiguous_sales'
ORDER BY m.event_date_local, c.summary, m.calendar_event_row
"""

dry_run = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
estimate = client.query(sql, location="asia-southeast1", job_config=dry_run)
if estimate.total_bytes_processed > 104857600:
    raise SystemExit("Stopped: estimated scan exceeds the 100 MiB safety limit.")

config = bigquery.QueryJobConfig(maximum_bytes_billed=104857600)
try:
    rows = client.query(sql, location="asia-southeast1", job_config=config).result()
    count = 0
    print("DATE       | REASON         | SALES OPTIONS | CALENDAR TITLE | EVENT ROW")
    for row in rows:
        count += 1
        title = " ".join((row.summary or "").split())
        print(f"{row.event_date_local} | {row.reason:<14} | "
              f"{row.sales_match_count:>13} | {title} | {row.calendar_event_row}")
    print(f"Total ambiguous events printed: {count}")
except Exception as exc:
    if "Custom quota exceeded" in str(exc):
        raise SystemExit("Daily BigQuery query cap reached; retry after reset.") from None
    raise
finally:
    client.close()
