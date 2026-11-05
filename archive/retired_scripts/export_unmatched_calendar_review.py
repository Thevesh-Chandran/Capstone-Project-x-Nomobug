"""Export unmatched or ambiguous 2026 Calendar events for private review."""
from pathlib import Path
import base64
import html
import sys
from urllib.parse import urlencode
from google.cloud import bigquery

if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] != '--ambiguous'):
    raise SystemExit('Usage: python scripts/export_unmatched_calendar_review.py [--ambiguous]')
review_status = 'ambiguous_sales' if '--ambiguous' in sys.argv else 'unmatched'
review_label = 'Ambiguous' if review_status == 'ambiguous_sales' else 'Unmatched'

root = Path(__file__).resolve().parents[1]
output = root / 'data' / 'exports' / 'calendar_review'
output.mkdir(parents=True, exist_ok=True)
client = bigquery.Client(project='profound-keel-500007-s4', location='asia-southeast1')
query = """
SELECT m.calendar_event_row, m.calendar_name, m.calendar_id, m.event_id,
       m.event_date_local, m.start_raw, m.event_category, m.match_status,
       m.phone_present, m.invoice_present, m.email_present,
       m.sales_match_count, m.invoice_match_count, m.phone_match_count,
       m.email_match_count, m.address_match_count,
       b.summary, b.description, b.location
FROM `profound-keel-500007-s4.silver.calendar_event_matches` m
JOIN `profound-keel-500007-s4.bronze.calendar_events_78147d417f3d97d3c1d9ef0be59638fd7850e4195108e1fc7b879483c7f35b66` b
  USING (calendar_event_row)
WHERE m.matching_scope = 'service_candidate' AND m.match_status = @review_status
  AND EXTRACT(YEAR FROM m.event_date_local) = 2026
ORDER BY m.event_date_local, m.calendar_name, m.event_id
"""
try:
    rows = list(client.query(query, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=104857600,
        query_parameters=[bigquery.ScalarQueryParameter(
            'review_status', 'STRING', review_status)])).result())
finally:
    client.close()

def escape(value):
    return html.escape(str(value or ''))

cards = []
for number, row in enumerate(rows, 1):
    # Calendar's event link encodes event ID and calendar ID together.
    eid = base64.urlsafe_b64encode(
        f"{row.event_id} {row.calendar_id}".encode()).decode().rstrip('=')
    link = 'https://calendar.google.com/calendar/event?' + urlencode({'eid': eid})
    reason = (
        'shared invoice' if row.invoice_match_count > 1 else
        'shared phone' if row.phone_match_count > 1 else
        'shared email' if row.email_match_count > 1 else
        'shared address' if row.address_match_count > 1 else 'not identified'
    )
    match_note = (f'<p><strong>Why ambiguous:</strong> {escape(reason)} · '
                  f'{row.sales_match_count} possible Sales records; none selected.</p>') \
                 if review_status == 'ambiguous_sales' else ''
    cards.append(f'''<article><h2>{number}. {escape(row.summary) or '(No title)'}</h2>
<p>{escape(row.event_date_local)} · {escape(row.calendar_name)} · {escape(row.event_category)}</p>
{match_note}
<p><a href="{escape(link)}" target="_blank" rel="noopener noreferrer">Open in Google Calendar</a></p>
<p>Snapshot event row: {escape(row.calendar_event_row)} · Start: {escape(row.start_raw)}</p>
<p>Parser detected phone: {row.phone_present} · invoice: {row.invoice_present} · email: {row.email_present}</p>
<details><summary>Show recorded description and location</summary>
<h3>Description</h3><pre>{escape(row.description) or '(Empty)'}</pre>
<h3>Location</h3><pre>{escape(row.location) or '(Empty)'}</pre></details></article>''')

page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Nomobug — REVIEW_LABEL_LOWER Calendar review</title>
<style>body{font:16px system-ui;max-width:1000px;margin:32px auto;padding:0 20px;background:#f5f7fa;color:#172330}article{background:white;padding:20px;margin:16px 0;border:1px solid #d9e1e8;border-radius:10px}h2{font-size:19px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px system-ui}summary,a{cursor:pointer;color:#0759a5}</style>
<h1>REVIEW_LABEL 2026 Calendar service candidates</h1>
<p>Private review of the stored snapshot. These are candidate service events, not verified completed visits. Current Calendar content may have changed since extraction. A missing parsed phone does not prove the description contains no phone.</p>
<p>Use the event number when reporting a correction. If an event link fails, find it using its date, calendar and title.</p>
'''
page = page.replace('REVIEW_LABEL_LOWER', review_label.lower()).replace('REVIEW_LABEL', review_label)
path = output / ('ambiguous_2026_events.html' if review_status == 'ambiguous_sales'
                 else 'unmatched_2026_events.html')
path.write_text(page + f'<p>Events: {len(rows)}</p>' + ''.join(cards) + '</html>', encoding='utf-8')
print(f'Exported {len(rows)} events to {path}')
print('Private local HTML only; source records unchanged.')
